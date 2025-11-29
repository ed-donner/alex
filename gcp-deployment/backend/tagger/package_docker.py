#!/usr/bin/env python3
"""
Package the Tagger Lambda function using Docker for AWS compatibility.
"""

import os
import sys
import shutil
import tempfile
import subprocess
import argparse
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and capture output."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout

def package_lambda():
    """Package the Lambda function with all dependencies."""
    
    # Get the directory containing this script
    tagger_dir = Path(__file__).parent.absolute()
    backend_dir = tagger_dir.parent
    
    # Create a temporary directory for packaging
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        package_dir = temp_path / "package"
        package_dir.mkdir()
        
        print("Creating Lambda package using Docker...")
        
        # Export exact requirements from uv.lock (excluding the editable database package)
        print("Exporting requirements from uv.lock...")
        requirements_result = run_command(
            ["uv", "export", "--no-hashes", "--no-emit-project"],
            cwd=str(tagger_dir)
        )

        # Filter out packages that don't work in Lambda
        filtered_requirements = []
        for line in requirements_result.splitlines():
            # Skip pyperclip (clipboard library not needed in Lambda)
            if line.startswith("pyperclip"):
                print(f"Excluding from Lambda: {line}")
                continue
            filtered_requirements.append(line)

        req_file = temp_path / "requirements.txt"
        req_file.write_text("\n".join(filtered_requirements))
        
        # Use Docker to install dependencies for Lambda's architecture
        docker_cmd = [
            "docker", "run", "--rm",
            "--platform", "linux/amd64",
            "-v", f"{temp_path}:/build",
            "-v", f"{backend_dir}/database:/database",
            "--entrypoint", "/bin/bash",
            "public.ecr.aws/lambda/python:3.12",
            "-c",
            """cd /build && pip install --target ./package -r requirements.txt && pip install --target ./package --no-deps /database"""
        ]
        
        run_command(docker_cmd)
        
        # Copy Lambda handler, agent, templates, and observability
        shutil.copy(tagger_dir / "lambda_handler.py", package_dir)
        shutil.copy(tagger_dir / "agent.py", package_dir)
        shutil.copy(tagger_dir / "templates.py", package_dir)
        shutil.copy(tagger_dir / "observability.py", package_dir)
        
        # Create the zip file
        zip_path = tagger_dir / "tagger_lambda.zip"
        
        # Remove old zip if it exists
        if zip_path.exists():
            zip_path.unlink()
        
        # Create new zip
        print(f"Creating zip file: {zip_path}")
        run_command(
            ["zip", "-r", str(zip_path), "."],
            cwd=str(package_dir)
        )
        
        # Get file size
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"Package created: {zip_path} ({size_mb:.1f} MB)")
        
        return zip_path

def deploy_lambda(zip_path):
    """Deploy the Lambda function to AWS."""
    import boto3
    
    lambda_client = boto3.client('lambda')
    function_name = 'alex-tagger'
    
    print(f"Deploying to Lambda function: {function_name}")
    
    try:
        # Try to update existing function
        with open(zip_path, 'rb') as f:
            response = lambda_client.update_function_code(
                FunctionName=function_name,
                ZipFile=f.read()
            )
        print(f"Successfully updated Lambda function: {function_name}")
        print(f"Function ARN: {response['FunctionArn']}")
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"Lambda function {function_name} not found. Please deploy via Terraform first.")
        sys.exit(1)
    except Exception as e:
        print(f"Error deploying Lambda: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Package Tagger Lambda for deployment')
    parser.add_argument('--deploy', action='store_true', help='Deploy to AWS after packaging')
    args = parser.parse_args()
    
    # Check if Docker is available
    try:
        run_command(["docker", "--version"])
    except FileNotFoundError:
        print("Error: Docker is not installed or not in PATH")
        sys.exit(1)
    
    # Package the Lambda
    zip_path = package_lambda()
    
    # Deploy if requested
    if args.deploy:
        deploy_lambda(zip_path)

if __name__ == "__main__":
    main()