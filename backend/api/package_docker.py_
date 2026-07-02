#!/usr/bin/env python3
"""
Package the FastAPI API for Lambda deployment using Docker.
This ensures binary compatibility with Lambda's runtime environment.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
import tempfile
import zipfile

def run_command(cmd, cwd=None):
    """Run a shell command and handle errors."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout

def main():
    # Get the API directory
    api_dir = Path(__file__).parent.absolute()
    backend_dir = api_dir.parent
    project_root = backend_dir.parent

    print(f"API directory: {api_dir}")
    print(f"Backend directory: {backend_dir}")

    # Check if Docker is running
    try:
        run_command(["docker", "info"])
    except Exception as e:
        print("Error: Docker is not running or not installed")
        print("Please ensure Docker Desktop is running and try again")
        sys.exit(1)

    # Create temp directory for packaging
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        package_dir = temp_path / "package"
        package_dir.mkdir()

        print(f"Packaging in: {package_dir}")

        # Copy API code
        api_package = package_dir / "api"
        shutil.copytree(api_dir, api_package, ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", ".env*", "*.zip", "package_docker.py", "test_*.py"
        ))

        # Copy lambda_handler.py to root level for Lambda to find it
        shutil.copy2(api_dir / "lambda_handler.py", package_dir / "lambda_handler.py")

        # Copy database package
        database_src = backend_dir / "database" / "src"
        database_dst = package_dir / "src"
        if database_src.exists():
            shutil.copytree(database_src, database_dst, ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc"
            ))
            print(f"Copied database package from {database_src}")
            
            # Verify database package was copied
            if (database_dst / "__init__.py").exists():
                print("✅ Database package copied successfully")
            else:
                print("⚠️ Warning: Database package may not have been copied correctly")
        else:
            print(f"❌ Error: Database package not found at {database_src}")
            sys.exit(1)

        # Create requirements.txt from pyproject.toml
        requirements_file = package_dir / "requirements.txt"
        with open(requirements_file, "w") as f:
            # Core dependencies
            f.write("fastapi>=0.116.0\n")
            f.write("uvicorn>=0.35.0\n")
            f.write("mangum>=0.19.0\n")
            f.write("boto3>=1.26.0\n")
            f.write("fastapi-clerk-auth>=0.0.7\n")
            f.write("pydantic>=2.0.0\n")
            f.write("python-dotenv>=1.0.0\n")
            f.write("python-jose>=3.5.0\n")
            f.write("httpx>=0.28.0\n")
            # Database dependencies
            f.write("sqlalchemy>=2.0.0\n")
            f.write("psycopg2-binary>=2.9.0\n")

        # Create Dockerfile
        dockerfile_content = """
FROM public.ecr.aws/lambda/python:3.12

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -t /var/task

# Copy application code
COPY . /var/task/

# Set the handler
CMD ["api.main.handler"]
"""

        dockerfile = package_dir / "Dockerfile"
        with open(dockerfile, "w") as f:
            f.write(dockerfile_content)

        # Build Docker image for x86_64 architecture (Lambda runtime)
        print("Building Docker image for x86_64 architecture...")
        run_command([
            "docker", "build",
            "--platform", "linux/amd64",
            "-t", "alex-api-packager",
            "."
        ], cwd=package_dir)

        # Create container and extract files
        print("Extracting Lambda package...")
        container_name = "alex-api-extract"

        # Remove container if it exists
        run_command(["docker", "rm", "-f", container_name], cwd=package_dir)

        # Create container
        run_command([
            "docker", "create",
            "--name", container_name,
            "alex-api-packager"
        ], cwd=package_dir)

        # Extract /var/task contents
        extract_dir = temp_path / "lambda"
        extract_dir.mkdir()

        run_command([
            "docker", "cp",
            f"{container_name}:/var/task/.",
            str(extract_dir)
        ])

        # Clean up container
        run_command(["docker", "rm", "-f", container_name])

        # Create the final zip
        zip_path = api_dir / "api_lambda.zip"
        print(f"Creating zip file: {zip_path}")

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(extract_dir):
                # Skip __pycache__ directories
                dirs[:] = [d for d in dirs if d != '__pycache__']

                for file in files:
                    # Skip .pyc files
                    if file.endswith('.pyc'):
                        continue

                    file_path = Path(root) / file
                    arcname = file_path.relative_to(extract_dir)
                    zipf.write(file_path, arcname)

        # Get file size
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"✅ Lambda package created: {zip_path} ({size_mb:.2f} MB)")

        # Verify the package
        print("\nPackage contents (first 20 files):")
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            files = zipf.namelist()[:20]
            for f in files:
                print(f"  - {f}")
            if len(zipf.namelist()) > 20:
                print(f"  ... and {len(zipf.namelist()) - 20} more files")

if __name__ == "__main__":
    main()