#!/usr/bin/env python3
"""
Destroy Aurora Serverless v2 Express cluster for Alex project.

WARNING: This permanently deletes the Aurora cluster and ALL data in it.
Only use when done developing or to rebuild the cluster from scratch.

Run from the bootstrap/ directory:
    uv run destroy_aurora_express.py

To rebuild afterwards:
    uv run setup_aurora_express.py
"""

import boto3
import subprocess
import sys
import time
from pathlib import Path

CLUSTER_ID    = "alex-aurora-cluster"

BOOTSTRAP_DIR = Path(__file__).parent
REPO_ROOT     = BOOTSTRAP_DIR.parent
DB_TF_DIR     = REPO_ROOT / "terraform" / "5_database"
AUTO_TFVARS   = DB_TF_DIR / "bootstrap.auto.tfvars.json"


def get_region() -> str:
    tfvars = DB_TF_DIR / "terraform.tfvars"
    for line in tfvars.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("aws_region") and "=" in stripped:
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    raise ValueError("aws_region not found in terraform/5_database/terraform.tfvars")


def tf(args: list[str]) -> None:
    cmd = ["terraform"] + args
    print(f"    $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=DB_TF_DIR)
    if result.returncode != 0:
        sys.exit(f"\n✗ terraform {args[0]} failed (exit {result.returncode})")


def main() -> None:
    print("\n" + "=" * 60)
    print("  Alex — Aurora Express Destroy")
    print("=" * 60)
    print("\n⚠️  This will DELETE the Aurora cluster and ALL DATA.\n")
    confirm = input("  Type 'yes' to confirm: ").strip().lower()
    if confirm != "yes":
        print("  Cancelled.")
        sys.exit(0)

    region = get_region()
    rds = boto3.client("rds", region_name=region)

    # ── 1. Delete cluster ────────────────────────────────────────────────────
    print(f"\n[1/3] Deleting cluster '{CLUSTER_ID}'")

    existing = rds.describe_db_clusters(
        Filters=[{"Name": "db-cluster-id", "Values": [CLUSTER_ID]}]
    )["DBClusters"]

    if not existing:
        print(f"  Cluster '{CLUSTER_ID}' not found — already deleted.")
    else:
        status = existing[0]["Status"]
        print(f"  Current status: {status}")

        # Stopped clusters must be started before instances can be deleted
        if status == "stopped":
            print("  Starting cluster so it can be deleted...")
            rds.start_db_cluster(DBClusterIdentifier=CLUSTER_ID)
            rds.get_waiter("db_cluster_available").wait(
                DBClusterIdentifier=CLUSTER_ID,
                WaiterConfig={"Delay": 15, "MaxAttempts": 40},
            )
            print("  Cluster started ✓")

        # Delete cluster member instances first (Express auto-creates one)
        for member in existing[0].get("DBClusterMembers", []):
            instance_id = member["DBInstanceIdentifier"]
            print(f"  Deleting instance '{instance_id}'...")
            try:
                rds.delete_db_instance(
                    DBInstanceIdentifier=instance_id,
                    SkipFinalSnapshot=True,
                )
            except Exception:
                pass  # already deleting or not found

        rds.delete_db_cluster(
            DBClusterIdentifier=CLUSTER_ID,
            SkipFinalSnapshot=True,
        )
        print("  Deletion requested. Waiting (final backup can take 15-20 min)...")
        for i in range(1, 181):  # up to 30 minutes
            time.sleep(10)
            remaining = rds.describe_db_clusters(
                Filters=[{"Name": "db-cluster-id", "Values": [CLUSTER_ID]}]
            )["DBClusters"]
            if not remaining:
                print(f"  Deleted ✓  ({i * 10}s)")
                break
            print(f"  ... still deleting ({remaining[0]['Status']}), {i * 10}s elapsed")
        else:
            sys.exit("  ✗ Cluster deletion timed out after 30 minutes")

    # ── 2. Remove bootstrap.auto.tfvars.json ────────────────────────────────
    print("\n[2/3] Removing bootstrap.auto.tfvars.json")
    if AUTO_TFVARS.exists():
        AUTO_TFVARS.unlink()
        print(f"  Removed: {AUTO_TFVARS.relative_to(REPO_ROOT)}")
    else:
        print("  Not found — already removed.")

    # ── 3. Update terraform state ────────────────────────────────────────────
    print("\n[3/3] Terraform apply (clearing cluster ARN from state)")
    tf(["apply", "-auto-approve"])

    print("\n✅  Aurora cluster destroyed.\n")
    print("  Terraform IAM role and Secrets Manager secret are still in place.")
    print("  To recreate the cluster:\n    uv run setup_aurora_express.py\n")
    print("  To fully destroy everything (including IAM + secret):")
    print("    cd terraform/5_database && terraform destroy\n")


if __name__ == "__main__":
    main()
