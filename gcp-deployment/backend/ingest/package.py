#!/usr/bin/env python3
"""
Cross-platform Lambda deployment package creator using uv.
Works on Windows, Mac, and Linux.
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path


def create_deployment_package():
    """Create a Lambda deployment package with dependencies from uv."""
    
    # Paths
    current_dir = Path(__file__).parent
    build_dir = current_dir / 'build'
    package_dir = build_dir / 'package'
    zip_path = current_dir / 'lambda_function.zip'
    venv_site_packages = current_dir / '.venv' / 'lib'
    
    # Clean up previous builds
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if zip_path.exists():
        os.remove(zip_path)
    
    # Create build directory
    package_dir.mkdir(parents=True, exist_ok=True)
    
    # Find the site-packages directory (cross-platform)
    site_packages = None
    for path in venv_site_packages.rglob('site-packages'):
        site_packages = path
        break
    
    if not site_packages or not site_packages.exists():
        print("Error: Could not find site-packages. Make sure you've run 'uv init' and 'uv add' for dependencies.")
        sys.exit(1)
    
    print(f"Copying dependencies from {site_packages}...")
    # Copy all dependencies to package directory
    for item in site_packages.iterdir():
        if item.name.endswith('.dist-info') or item.name == '__pycache__':
            continue
        if item.is_dir():
            shutil.copytree(item, package_dir / item.name, dirs_exist_ok=True)
        else:
            shutil.copy2(item, package_dir)
    
    # Copy Lambda function code
    print("Copying Lambda function code...")
    
    # Copy S3 Vectors Lambda handlers
    if (current_dir / 'ingest_s3vectors.py').exists():
        shutil.copy(current_dir / 'ingest_s3vectors.py', package_dir)
    if (current_dir / 'search_s3vectors.py').exists():
        shutil.copy(current_dir / 'search_s3vectors.py', package_dir)
    
    # Create ZIP file
    print("Creating deployment package...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_dir):
            # Skip __pycache__ directories
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for file in files:
                if file.endswith('.pyc'):
                    continue
                file_path = Path(root) / file
                arcname = file_path.relative_to(package_dir)
                zipf.write(file_path, arcname)
    
    # Clean up build directory
    shutil.rmtree(build_dir)
    
    # Get file size
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"\n✅ Deployment package created: {zip_path}")
    print(f"   Size: {size_mb:.2f} MB")
    
    if size_mb > 50:
        print("⚠️  Warning: Package exceeds 50MB. Consider using Lambda Layers.")
    
    return str(zip_path)


if __name__ == '__main__':
    create_deployment_package()