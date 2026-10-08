#!/usr/bin/env python3
"""
Setup Aurora Serverless v2 with Express Configuration for Alex project.

AWS free-tier accounts cannot create Aurora clusters via Terraform because they
require the --with-express-configuration flag, which the Terraform AWS provider
does not support. This script handles the full cluster lifecycle outside Terraform,
then synchronises the result back into Terraform state so downstream modules
(6_agents, 7_frontend) continue to work unchanged.

What this script does:
  1. terraform init + apply in 5_database  (creates Secrets Manager secret + IAM)
  2. Creates Aurora Express cluster via boto3
  3. Enables the Data API  (uses enable_http_endpoint, NOT modify_db_cluster)
  4. Sets the master password to match the Terraform-managed secret
  5. Creates the 'alex' database
  6. Writes terraform/5_database/bootstrap.auto.tfvars.json  (cluster ARN)
  7. terraform apply again  (records cluster ARN in state / outputs)

Run from the bootstrap/ directory:
    uv run setup_aurora_express.py
"""

import boto3
import botocore.exceptions
import json
import subprocess
import sys
import time
from pathlib import Path

from tenacity import Retrying, retry_if_exception_type, stop_after_delay, wait_exponential

# ── Configuration ─────────────────────────────────────────────────────────────
CLUSTER_ID     = "alex-aurora-cluster"
MASTER_USER    = "alexadmin"
DATABASE_NAME  = "alex"

# Serverless v2 scaling capacity (Aurora Capacity Units).
# MIN_CAPACITY = 0.0 enables auto-pause when idle — keeps costs near zero
# for dev/free-tier use.  Raise MAX_CAPACITY for heavier workloads.
MIN_CAPACITY = 0.0   # 0.0 = auto-pause enabled
MAX_CAPACITY = 4.0   # Aurora Express default

BOOTSTRAP_DIR  = Path(__file__).parent
REPO_ROOT      = BOOTSTRAP_DIR.parent
DB_TF_DIR      = REPO_ROOT / "terraform" / "5_database"
AUTO_TFVARS    = DB_TF_DIR / "bootstrap.auto.tfvars.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_region() -> str:
    """Read aws_region from terraform/5_database/terraform.tfvars."""
    tfvars = DB_TF_DIR / "terraform.tfvars"
    for line in tfvars.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("aws_region") and "=" in stripped:
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    raise ValueError("aws_region not found in terraform/5_database/terraform.tfvars")


def tf(args: list[str]) -> None:
    """Run a terraform command, fail fast on non-zero exit."""
    cmd = ["terraform"] + args
    print(f"    $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=DB_TF_DIR)
    if result.returncode != 0:
        sys.exit(f"\n✗ terraform {args[0]} failed (exit {result.returncode})")


def tf_output(key: str) -> str:
    """Return a single terraform output value as a string."""
    result = subprocess.run(
        ["terraform", "output", "-raw", key],
        cwd=DB_TF_DIR, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def poll(check_fn, label: str, interval: int = 10, timeout: int = 600) -> None:
    """Block until check_fn() returns True or timeout seconds elapse."""
    elapsed = 0
    while elapsed < timeout:
        if check_fn():
            return
        print(f"    ⏳ {label} ({elapsed}s elapsed, retrying in {interval}s)")
        time.sleep(interval)
        elapsed += interval
    raise TimeoutError(f"Timed out after {timeout}s waiting for: {label}")


def rds_execute(rds_data, max_attempts: int = 36, delay: int = 10, **kwargs) -> dict:
    """
    Execute a Data API statement with retry for transient Aurora startup errors.

    Aurora Express frequently returns transient errors while resuming from
    auto-pause or while the HTTP endpoint is still initialising.
    """
    transient_codes = {
        "DatabaseResumingException",
        "DatabaseUnavailableException",
        "HttpEndpointNotEnabledException",
        "InvalidResourceStateException",
        # Password propagation after modify_db_cluster can take 30-60s; the
        # cluster reports "available" before PostgreSQL picks up the new credential.
        "DatabaseErrorException",
    }
    transient_phrases = [
        "Aurora is starting up",
        "resuming after being auto-paused",
        "HttpEndpoint is being enabled",
        "Communications link failure",
        "password authentication failed",
    ]

    for attempt in range(1, max_attempts + 1):
        try:
            return rds_data.execute_statement(**kwargs)
        except botocore.exceptions.ClientError as exc:
            code = exc.response["Error"]["Code"]
            msg  = str(exc)
            # DatabaseErrorException wraps real SQL errors too; only retry it
            # when the message matches a known transient phrase.
            if code == "DatabaseErrorException":
                transient = any(p in msg for p in transient_phrases)
            else:
                transient = code in transient_codes or any(p in msg for p in transient_phrases)
            if transient and attempt < max_attempts:
                print(f"    ⏳ Aurora not ready ({code}), attempt {attempt}/{max_attempts}, waiting {delay}s")
                time.sleep(delay)
            else:
                raise

    raise TimeoutError("Aurora did not become ready within the retry window.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 60)
    print("  Alex — Aurora Express Setup")
    print("=" * 60)

    region = get_region()
    print(f"\n  Region : {region}")

    rds      = boto3.client("rds",             region_name=region)
    sm       = boto3.client("secretsmanager",  region_name=region)
    rds_data = boto3.client("rds-data",        region_name=region)

    # ── 1. Terraform: create Secrets Manager secret + IAM role ───────────────
    print("\n[1/7] Terraform init + apply (Secrets Manager + IAM)")
    tf(["init", "-upgrade"])
    tf(["apply", "-auto-approve"])

    secret_arn = tf_output("aurora_secret_arn")
    print(f"  Secret ARN : {secret_arn}")

    secret_string = json.loads(
        sm.get_secret_value(SecretId=secret_arn)["SecretString"]
    )
    db_password = secret_string["password"]
    print("  Password read from Secrets Manager ✓")

    # ── 2. Create Aurora Express cluster ────────────────────────────────────
    print(f"\n[2/7] Aurora Express cluster '{CLUSTER_ID}'")

    existing = rds.describe_db_clusters(
        Filters=[{"Name": "db-cluster-id", "Values": [CLUSTER_ID]}]
    )["DBClusters"]

    if existing:
        cluster_arn = existing[0]["DBClusterArn"]
        print(f"  Already exists: {cluster_arn}")
    else:
        print("  Creating cluster (this takes a few minutes)...")
        rds.create_db_cluster(
            DBClusterIdentifier=CLUSTER_ID,
            Engine="aurora-postgresql",
            MasterUsername=MASTER_USER,
            WithExpressConfiguration=True,
        )
        rds.get_waiter("db_cluster_available").wait(
            DBClusterIdentifier=CLUSTER_ID,
            WaiterConfig={"Delay": 15, "MaxAttempts": 60},
        )
        cluster_arn = rds.describe_db_clusters(
            DBClusterIdentifier=CLUSTER_ID
        )["DBClusters"][0]["DBClusterArn"]
        print(f"  Created: {cluster_arn}")

    # ── 3. Enable Data API ──────────────────────────────────────────────────
    # IMPORTANT: use enable_http_endpoint(), NOT modify_db_cluster().
    # modify_db_cluster(enable_http_endpoint=True) silently does nothing on Express.
    print("\n[3/7] Data API")

    http_enabled = rds.describe_db_clusters(
        DBClusterIdentifier=CLUSTER_ID
    )["DBClusters"][0].get("HttpEndpointEnabled", False)

    if http_enabled:
        print("  Already enabled ✓")
    else:
        rds.enable_http_endpoint(ResourceArn=cluster_arn)
        print("  Enabling Data API endpoint, polling until ready...")
        poll(
            lambda: rds.describe_db_clusters(
                DBClusterIdentifier=CLUSTER_ID
            )["DBClusters"][0].get("HttpEndpointEnabled", False),
            label="Data API to be enabled",
        )
        print("  Enabled ✓  (waiting for cluster to finish modifying)")
        rds.get_waiter("db_cluster_available").wait(
            DBClusterIdentifier=CLUSTER_ID,
            WaiterConfig={"Delay": 10, "MaxAttempts": 60},
        )
        print("  Data API ready ✓")

    # ── 4. Set master password + capacity ───────────────────────────────────
    print("\n[4/7] Syncing cluster password and capacity")

    # Data API enable can leave the cluster briefly in "modifying" even after
    # the waiter returns.  Use tenacity to retry the modify until the cluster
    # accepts it, waiting for available inside each attempt.
    for attempt in Retrying(
        retry=retry_if_exception_type(rds.exceptions.InvalidDBClusterStateFault),
        wait=wait_exponential(min=5, max=30),
        stop=stop_after_delay(300),
        reraise=True,
        before_sleep=lambda _: print("  Cluster not yet accepting modifications, retrying..."),
    ):
        with attempt:
            rds.get_waiter("db_cluster_available").wait(
                DBClusterIdentifier=CLUSTER_ID,
                WaiterConfig={"Delay": 10, "MaxAttempts": 60},
            )
            rds.modify_db_cluster(
                DBClusterIdentifier=CLUSTER_ID,
                MasterUserPassword=db_password,
                ServerlessV2ScalingConfiguration={
                    "MinCapacity": MIN_CAPACITY,
                    "MaxCapacity": MAX_CAPACITY,
                },
                ApplyImmediately=True,
            )

    print("  Password change applied, waiting for cluster ...")
    rds.get_waiter("db_cluster_available").wait(
        DBClusterIdentifier=CLUSTER_ID,
        WaiterConfig={"Delay": 10, "MaxAttempts": 60},
    )
    # Password propagation to PostgreSQL is handled by rds_execute retrying on
    # DatabaseErrorException / "password authentication failed".
    print("  Password synced ✓")

    # ── 5. Create 'alex' database ────────────────────────────────────────────
    print(f"\n[5/7] Database '{DATABASE_NAME}'")

    # Query postgres system database first (default database for admin tasks).
    # rds_execute retries DatabaseErrorException so password propagation delay
    # (up to 60s after modify_db_cluster) is handled automatically.
    row = rds_execute(
        rds_data,
        max_attempts=60,
        delay=10,
        resourceArn=cluster_arn,
        secretArn=secret_arn,
        database="postgres",
        sql=f"SELECT 1 FROM pg_database WHERE datname = '{DATABASE_NAME}'",
    )
    if row.get("records"):
        print(f"  '{DATABASE_NAME}' already exists ✓")
    else:
        rds_execute(
            rds_data,
            max_attempts=60,
            delay=10,
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database="postgres",
            sql=f"CREATE DATABASE {DATABASE_NAME}",
        )
        print(f"  '{DATABASE_NAME}' created ✓")

    # ── 6. Write bootstrap.auto.tfvars.json ─────────────────────────────────
    print("\n[6/7] Writing bootstrap.auto.tfvars.json")

    AUTO_TFVARS.write_text(
        json.dumps({"aurora_cluster_arn": cluster_arn}, indent=2) + "\n"
    )
    print(f"  Written: {AUTO_TFVARS.relative_to(REPO_ROOT)}")

    # ── 7. Terraform apply: record cluster ARN in state/outputs ─────────────
    print("\n[7/7] Terraform apply (record cluster ARN in state)")
    tf(["apply", "-auto-approve"])

    # ── Done ─────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  ✅  Aurora Express cluster ready!")
    print("=" * 60)
    print(f"""
  Cluster ARN : {cluster_arn}
  Secret ARN  : {secret_arn}
  Database    : {DATABASE_NAME}
  Data API    : enabled

  Next — run the database setup from backend/database/:
    uv run test_data_api.py
    uv run run_migrations.py
    uv run seed_data.py
    uv run reset_db.py --with-test-data
    uv run verify_database.py
""")


if __name__ == "__main__":
    main()
