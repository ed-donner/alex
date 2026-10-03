#!/usr/bin/env python3
"""
Deploy researcher service to AWS Lambda.
Cross-platform deployment script for Mac/Windows/Linux.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)


def run_command(cmd, capture_output=False, cwd=None):
    """Run a command and handle errors."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=True,
            cwd=cwd,
        )
        if capture_output:
            return result.stdout.strip()
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        if e.stderr:
            print(f"Error details: {e.stderr}")
        sys.exit(1)


def terraform_apply(terraform_dir: Path, targets: list[str] | None = None):
    command = ["terraform", "apply", "-auto-approve"]
    for target in targets or []:
        command.extend(["-target", target])
    run_command(command, cwd=terraform_dir)


def terraform_output(terraform_dir: Path, output_name: str) -> str:
    return run_command(
        ["terraform", "output", "-raw", output_name],
        capture_output=True,
        cwd=terraform_dir,
    )


def get_repo_root() -> Path:
    return Path(
        run_command(["git", "rev-parse", "--show-toplevel"], capture_output=True)
    )


def write_image_override(terraform_dir: Path, image_uri: str):
    override_path = terraform_dir / "researcher.auto.tfvars.json"
    override_path.write_text(json.dumps({"researcher_image_uri": image_uri}, indent=2) + "\n")


def wait_for_lambda_active(region: str, function_name: str):
    print("\nWaiting for Lambda update to complete...")
    for _ in range(60):
        status = run_command(
            [
                "aws",
                "lambda",
                "get-function",
                "--function-name",
                function_name,
                "--region",
                region,
                "--query",
                "Configuration.LastUpdateStatus",
                "--output",
                "text",
            ],
            capture_output=True,
        ).strip()
        state = run_command(
            [
                "aws",
                "lambda",
                "get-function",
                "--function-name",
                function_name,
                "--region",
                region,
                "--query",
                "Configuration.State",
                "--output",
                "text",
            ],
            capture_output=True,
        ).strip()

        if status == "Successful" and state == "Active":
            print("✅ Lambda is active.")
            return
        if status == "Failed":
            print("❌ Lambda update failed. Check the AWS Console or CloudWatch logs.")
            sys.exit(1)

        print(".", end="", flush=True)
        time.sleep(5)

    print("\n⚠️ Lambda update is taking longer than expected.")


def main():
    print("Alex Researcher Service - Lambda Deployment")
    print("==========================================")

    # Get AWS account ID
    region = os.environ.get("DEFAULT_AWS_REGION")
    if not region:
        print("Error: DEFAULT_AWS_REGION not found in your .env file.")
        sys.exit(1)

    print("\nGetting AWS account details...")
    account_id = run_command(
        ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
        capture_output=True,
    )

    print(f"AWS Account: {account_id}")
    print(f"Region: {region}")

    repo_root = get_repo_root()
    terraform_dir = repo_root / "terraform" / "4_researcher"
    backend_dir = repo_root / "backend" / "researcher"

    print("\nEnsuring Terraform ECR prerequisites exist...")
    terraform_apply(
        terraform_dir,
        targets=[
            "aws_ecr_repository.researcher",
            "aws_ecr_repository_policy.researcher_lambda_access",
        ],
    )

    print("\nGetting ECR repository URL...")
    ecr_url = terraform_output(terraform_dir, "ecr_repository_url")
    if not ecr_url:
        print("Error: ECR repository not found.")
        sys.exit(1)

    print(f"ECR Repository: {ecr_url}")

    # Login to ECR
    print("\nLogging in to ECR...")
    password = run_command(
        ["aws", "ecr", "get-login-password", "--region", region], capture_output=True
    )

    login_process = subprocess.Popen(
        ["docker", "login", "--username", "AWS", "--password-stdin", ecr_url],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    _, stderr = login_process.communicate(input=password)
    if login_process.returncode != 0:
        print(f"Error logging into ECR: {stderr}")
        sys.exit(1)
    print("Login successful!")

    # Generate a unique tag using timestamp
    image_tag = f"deploy-{int(time.time())}"
    local_image = f"alex-researcher:{image_tag}"
    remote_image = f"{ecr_url}:{image_tag}"

    # Build Docker image
    print(f"\nBuilding Docker image for linux/amd64 with tag: {image_tag}")
    run_command(
        [
            "docker",
            "build",
            "--platform",
            "linux/amd64",
            "-t",
            local_image,
            ".",
        ],
        cwd=backend_dir,
    )

    # Tag for ECR
    print("\nTagging image for ECR...")
    run_command(["docker", "tag", local_image, remote_image])

    # Push to ECR
    print("\nPushing image to ECR...")
    run_command(["docker", "push", remote_image])
    print("\n✅ Docker image pushed successfully!")

    print("\nApplying Terraform with the new image...")
    write_image_override(terraform_dir, remote_image)
    terraform_apply(terraform_dir)

    function_name = terraform_output(terraform_dir, "researcher_function_name")
    service_url = terraform_output(terraform_dir, "researcher_url")

    wait_for_lambda_active(region, function_name)

    print("\n🚀 Your service is available at:")
    print(f"   {service_url}")
    print("\nTest it with:")
    print(f"   curl {service_url.rstrip('/')}/health")


if __name__ == "__main__":
    main()
