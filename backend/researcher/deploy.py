#!/usr/bin/env python3
"""
Deploy researcher service to AWS App Runner
Cross-platform deployment script for Mac/Windows/Linux
"""

import subprocess
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from the project root .env file regardless of cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)


def run_command(cmd, capture_output=False, shell=False):
    """Run a command and handle errors."""
    try:
        result = subprocess.run(
            cmd, shell=shell, capture_output=capture_output, text=True, check=True
        )
        if capture_output:
            return result.stdout.strip()
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        if e.stderr:
            print(f"Error details: {e.stderr}")
        sys.exit(1)


def main():
    print("Alex Researcher Service - Docker Deployment")
    print("===========================================")

    # Get AWS account ID
    print("\nGetting AWS account details...")
    account_id = run_command(
        ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
        capture_output=True,
    )

    region = os.environ.get("DEFAULT_AWS_REGION")
    if not region:
        print("Error: DEFAULT_AWS_REGION not found in your .env file.")
        sys.exit(1)

    ecr_repository = "alex-researcher"

    print(f"AWS Account: {account_id}")
    print(f"Region: {region}")

    # Get ECR repository URL from Terraform
    print("\nGetting ECR repository URL...")
    terraform_dir = Path(__file__).parent.parent.parent / "terraform" / "4_researcher"
    original_dir = os.getcwd()

    try:
        os.chdir(terraform_dir)
        ecr_url = run_command(
            ["terraform", "output", "-raw", "ecr_repository_url"], capture_output=True
        )
    finally:
        os.chdir(original_dir)

    if not ecr_url:
        print("Error: ECR repository not found. Run 'terraform apply' first.")
        sys.exit(1)

    print(f"ECR Repository: {ecr_url}")

    # Login to ECR
    print("\nLogging in to ECR...")
    password = run_command(
        ["aws", "ecr", "get-login-password", "--region", region], capture_output=True
    )

    login_cmd = ["docker", "login", "--username", "AWS", "--password-stdin", ecr_url]
    login_process = subprocess.Popen(
        login_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    stdout, stderr = login_process.communicate(input=password)

    if login_process.returncode != 0:
        print(f"Error logging into ECR: {stderr}")
        sys.exit(1)

    print("Login successful!")

    # Generate a unique tag using timestamp
    import time

    timestamp = int(time.time())
    image_tag = f"deploy-{timestamp}"

    # Build Docker image
    print(f"\nBuilding Docker image for linux/amd64 with tag: {image_tag}")
    print("(This ensures compatibility with AWS App Runner)")
    run_command(
        [
            "docker",
            "build",
            "--platform",
            "linux/amd64",
            "-t",
            f"{ecr_repository}:{image_tag}",
            # Removed --no-cache to use Docker layer caching for faster builds
            ".",
        ]
    )

    # Tag for ECR with both unique tag and latest
    print("\nTagging image for ECR...")
    run_command(["docker", "tag", f"{ecr_repository}:{image_tag}", f"{ecr_url}:{image_tag}"])
    run_command(["docker", "tag", f"{ecr_repository}:{image_tag}", f"{ecr_url}:latest"])

    # Push to ECR
    print("\nPushing image to ECR...")
    run_command(["docker", "push", f"{ecr_url}:{image_tag}"])
    run_command(["docker", "push", f"{ecr_url}:latest"])

    print("\n✅ Docker image pushed successfully!")
    print(
        "\nNext step: Run 'terraform apply' in terraform/4_researcher to create or update the ECS service."
    )

    # If the ECS service already exists, trigger a fresh deployment so it pulls latest.
    print("\nChecking for existing ECS service...")
    try:
        service_status = run_command(
            [
                "aws",
                "ecs",
                "describe-services",
                "--cluster",
                "alex-researcher",
                "--services",
                "alex-researcher",
                "--region",
                region,
                "--query",
                "services[0].status",
                "--output",
                "text",
            ],
            capture_output=True,
        )

        if service_status and service_status.strip() != "None":
            print("Found ECS service. Starting a new deployment...")
            run_command(
                [
                    "aws",
                    "ecs",
                    "update-service",
                    "--cluster",
                    "alex-researcher",
                    "--service",
                    "alex-researcher",
                    "--force-new-deployment",
                    "--region",
                    region,
                ],
                capture_output=True,
            )
            print("✅ ECS service deployment started.")
        else:
            print("ECS service not found yet. Run Terraform to create it.")
    except Exception as e:
        print(f"\nCouldn't automatically start deployment: {e}")
        print("\nTo deploy manually, run:")
        print("  cd terraform/4_researcher")
        print("  terraform apply")


if __name__ == "__main__":
    main()
