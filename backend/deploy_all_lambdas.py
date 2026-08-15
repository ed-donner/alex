#!/usr/bin/env python3
"""
Deploy all Lambda functions (Part 6 Agent Orchestra + Part 4 Researcher & Scheduler) to AWS using Terraform.
This script ensures all Lambda functions are properly updated by:
1. Optionally packaging the Lambda functions (including the scheduler Lambda)
2. Tainting Lambda resources in Terraform to force recreation
3. Running terraform apply to deploy both 6_agents and 4_researcher with the latest code

Usage:
    cd backend
    uv run deploy_all_lambdas.py [--package]
    
Options:
    --package    Force re-packaging of all Lambda functions before deployment
"""

import boto3
import sys
import subprocess
import os
from pathlib import Path
from typing import List, Tuple


def taint_and_deploy_via_terraform() -> bool:
    """
    Deploy all Lambda functions using Terraform with forced recreation.
    
    Returns:
        True if successful, False otherwise
    """
    backend_dir = Path(__file__).parent
    terraform_dir = backend_dir.parent / "terraform" / "6_agents"
    researcher_tf_dir = backend_dir.parent / "terraform" / "4_researcher"
    
    if not terraform_dir.exists():
        print(f"❌ Terraform directory not found: {terraform_dir}")
        return False
    
    # Lambda function names to taint in Part 6
    lambda_functions = ['planner', 'tagger', 'reporter', 'charter', 'retirement']
    
    print("📌 Step 1: Tainting Agent Orchestra Lambda functions to force recreation...")
    print("-" * 50)
    
    # Taint each Agent Lambda function in Part 6
    for func in lambda_functions:
        print(f"   Tainting aws_lambda_function.{func}...")
        result = subprocess.run(
            ['terraform', 'taint', f'aws_lambda_function.{func}'],
            cwd=terraform_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 or "already" in result.stderr:
            print(f"      ✓ {func} marked for recreation")
        elif "No such resource instance" in result.stderr:
            print(f"      ⚠️ {func} doesn't exist (will be created)")
        else:
            print(f"      ⚠️ Warning: {result.stderr[:100]}")
    
    print()
    print("🚀 Step 2: Running terraform apply for 6_agents...")
    print("-" * 50)
    
    # Run terraform apply for Part 6
    result = subprocess.run(
        ['terraform', 'apply', '-auto-approve'],
        cwd=terraform_dir,
        capture_output=False,
        text=True
    )
    
    if result.returncode != 0:
        print("❌ Agent Orchestra Terraform deployment failed!")
        return False
        
    print("✅ Agent Orchestra Lambda deployment completed successfully!")

    # Always deploy Scheduler and Researcher Lambda in Part 4
    if researcher_tf_dir.exists():
        print()
        print("⏰ Step 3: Deploying Researcher & Scheduler Lambdas (4_researcher)...")
        print("-" * 50)
        
        # Taint scheduler Lambda
        print("   Tainting aws_lambda_function.scheduler_lambda...")
        subprocess.run(
            ['terraform', 'taint', 'aws_lambda_function.scheduler_lambda'],
            cwd=researcher_tf_dir,
            capture_output=True,
            text=True
        )
        
        # Taint researcher Lambda if deployed
        subprocess.run(
            ['terraform', 'taint', 'aws_lambda_function.researcher[0]'],
            cwd=researcher_tf_dir,
            capture_output=True,
            text=True
        )

        res = subprocess.run(
            ['terraform', 'apply', '-auto-approve'],
            cwd=researcher_tf_dir,
            capture_output=False,
            text=True
        )
        if res.returncode == 0:
            print("✅ Researcher & Scheduler Lambdas deployed successfully!")
        else:
            print("⚠️ Researcher/Scheduler deployment failed!")
            return False

    return True


def package_lambda(service_name: str, service_dir: Path) -> bool:
    """
    Package a Lambda function using package_docker.py or package_scheduler.py.
    
    Args:
        service_name: Name of the service (e.g., 'planner', 'scheduler')
        service_dir: Path to the service directory
        
    Returns:
        True if successful, False otherwise
    """
    print(f"   📦 Packaging {service_name}...")
    
    if service_name == 'scheduler':
        package_script = service_dir.parent / 'package_scheduler.py'
        cmd = ['uv', 'run', 'package_scheduler.py']
        exec_dir = service_dir.parent
    else:
        package_script = service_dir / 'package_docker.py'
        cmd = ['uv', 'run', 'package_docker.py']
        exec_dir = service_dir

    if not package_script.exists():
        print(f"      ✗ Packaging script not found at {package_script}")
        return False
    
    try:
        result = subprocess.run(
            cmd,
            cwd=exec_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            zip_path = service_dir / 'lambda_function.zip' if service_name == 'scheduler' else service_dir / f'{service_name}_lambda.zip'
            if zip_path.exists():
                size_mb = zip_path.stat().st_size / (1024 * 1024)
                print(f"      ✓ Created {size_mb:.1f} MB package ({zip_path.name})")
                return True
            else:
                print(f"      ✗ Package not created")
                return False
        else:
            print(f"      ✗ Packaging failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"      ✗ Error running packaging script: {e}")
        return False


def main():
    """Main deployment function."""
    force_package = '--package' in sys.argv
    
    print("🎯 Deploying All Alex Lambda Functions (Part 6 Agents + Part 4 Researcher/Scheduler)")
    print("=" * 70)
    
    try:
        sts_client = boto3.client('sts')
        account_id = sts_client.get_caller_identity()['Account']
        region = boto3.Session().region_name
        print(f"AWS Account: {account_id}")
        print(f"AWS Region: {region}")
    except Exception as e:
        print(f"❌ Failed to get AWS account info: {e}")
        print("   Make sure your AWS credentials are configured")
        sys.exit(1)
    
    print()
    
    backend_dir = Path(__file__).parent
    services = [
        ('planner', backend_dir / 'planner' / 'planner_lambda.zip'),
        ('tagger', backend_dir / 'tagger' / 'tagger_lambda.zip'),
        ('reporter', backend_dir / 'reporter' / 'reporter_lambda.zip'),
        ('charter', backend_dir / 'charter' / 'charter_lambda.zip'),
        ('retirement', backend_dir / 'retirement' / 'retirement_lambda.zip'),
        ('scheduler', backend_dir / 'scheduler' / 'lambda_function.zip'),
    ]
    
    print("📋 Checking deployment packages...")
    services_to_package = []
    
    for service_name, zip_path in services:
        service_dir = backend_dir / service_name
        
        if force_package:
            services_to_package.append((service_name, service_dir))
            print(f"   ⟳ {service_name}: Will re-package")
        elif zip_path.exists():
            size_mb = zip_path.stat().st_size / (1024 * 1024)
            print(f"   ✓ {service_name}: {size_mb:.1f} MB")
        else:
            print(f"   ✗ {service_name}: Not found")
            services_to_package.append((service_name, service_dir))
    
    if services_to_package:
        print()
        print("📦 Packaging Lambda functions...")
        failed_packages = []
        
        for service_name, service_dir in services_to_package:
            if not package_lambda(service_name, service_dir):
                failed_packages.append(service_name)
        
        if failed_packages:
            print()
            print(f"❌ Failed to package: {', '.join(failed_packages)}")
            print("   Make sure Docker/Poetry is available")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                sys.exit(1)
    
    print()
    
    if taint_and_deploy_via_terraform():
        print()
        print("🎉 All Alex Lambda functions deployed successfully!")
        sys.exit(0)
    else:
        print()
        print("❌ Deployment failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()