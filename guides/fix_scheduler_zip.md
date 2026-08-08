# Plan: Package Scheduler Lambda Code and Dependencies

## Goal Description
To run the new refactored scheduler Lambda on AWS, we need to package its code (`lambda_function.py` and `config/` directory) along with the external `loguru` library into a deployment zip file before running `terraform apply`.

We will create a script [package_scheduler.py](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/package_scheduler.py) directly in the `backend/` directory (matching the style of `package_docker.py`).

The script will:
1. Query Poetry for the active virtualenv path.
2. Locate and copy the `loguru` dependency from site-packages.
3. Package the scheduler's files and the dependency into [lambda_function.zip](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/scheduler/lambda_function.zip).

---

## User Review Required
Before running the packaging script, ensure you have run `poetry install` in `backend/` so that the virtual environment contains the `loguru` package.

---

## Proposed Changes

### Backend Packaging Script
Create the [package_scheduler.py](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/package_scheduler.py) file in the `backend/` directory.

#### [NEW] [package_scheduler.py](file:///Users/aponte/personal_workspace/agent_engineering_production_udemy/projects/alex/backend/package_scheduler.py)

```python
import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

def create_deployment_package():
    current_dir = Path(__file__).parent  # backend/
    scheduler_dir = current_dir / 'scheduler'
    build_dir = scheduler_dir / 'build'
    package_dir = build_dir / 'package'
    zip_path = scheduler_dir / 'lambda_function.zip'

    # Get virtual env path from poetry
    try:
        venv_path = subprocess.check_output(
            ["poetry", "env", "info", "--path"],
            cwd=current_dir,
            text=True
        ).strip()
    except subprocess.CalledProcessError as e:
        print("Error: Could not find Poetry virtualenv. Run 'poetry install' in the backend/ directory first.")
        sys.exit(1)

    venv_site_packages = Path(venv_path) / 'lib'

    # Clean up previous builds
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if zip_path.exists():
        os.remove(zip_path)

    package_dir.mkdir(parents=True, exist_ok=True)

    # Find the site-packages directory (cross-platform support)
    site_packages = None
    for path in venv_site_packages.rglob('site-packages'):
        site_packages = path
        break

    if not site_packages or not site_packages.exists():
        print(f"Error: Could not find site-packages in {venv_site_packages}")
        sys.exit(1)

    print(f"Copying dependencies from {site_packages}...")
    # Package loguru (the only external dependency used by scheduler)
    dependencies_to_copy = ['loguru']
    for dep in dependencies_to_copy:
        dep_path = site_packages / dep
        if dep_path.exists() and dep_path.is_dir():
            shutil.copytree(dep_path, package_dir / dep, dirs_exist_ok=True)
        elif (site_packages / f"{dep}.py").exists():
            shutil.copy(site_packages / f"{dep}.py", package_dir)
        else:
            print(f"Warning: Dependency {dep} not found in site-packages.")

    # Copy Lambda function code and config folder
    print("Copying Lambda function code...")
    shutil.copy(scheduler_dir / 'lambda_function.py', package_dir)
    
    if (scheduler_dir / 'config').exists():
        shutil.copytree(scheduler_dir / 'config', package_dir / 'config', dirs_exist_ok=True)

    # Create ZIP file
    print("Creating deployment package...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_dir):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for file in files:
                if file.endswith('.pyc'):
                    continue
                file_path = Path(root) / file
                arcname = file_path.relative_to(package_dir)
                zipf.write(file_path, arcname)

    shutil.rmtree(build_dir)
    print(f"✅ Deployment package created: {zip_path}")
    print(f"   Size: {zip_path.stat().st_size / 1024:.2f} KB")

if __name__ == '__main__':
    create_deployment_package()
```

---

## Verification Plan

### Automated Tests
1. Run the packaging script from the `backend/` folder:
   ```bash
   poetry run python package_scheduler.py
   ```
2. Verify that `scheduler/lambda_function.zip` is successfully updated.
3. Run `terraform plan` in `terraform/4_researcher/` and ensure Terraform detects the changed code hash (`source_code_hash`).
