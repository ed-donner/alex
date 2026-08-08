#!/usr/bin/env python3
"""
Fast Frontend Deployment Script for Alex Financial Advisor.
Builds Next.js frontend and uploads assets to S3 + invalidates CloudFront cache
without re-packaging Lambda or running Terraform apply.
"""

import sys
import os
import json
import subprocess
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"


def run_command(cmd, cwd=None, check=True, capture_output=False, env=None):
    print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    if capture_output:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=isinstance(cmd, str), env=env)
        if check and result.returncode != 0:
            print(f"Error: {result.stderr}")
            sys.exit(1)
        return result.stdout.strip()
    else:
        result = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), env=env)
        if check and result.returncode != 0:
            sys.exit(1)
        return None


def main():
    print("🎨 Fast Frontend S3 Deployment")
    print("=" * 50)

    # 1. Fetch Terraform outputs from terraform/7_frontend
    tf_dir = Path(__file__).parent.parent / "terraform" / "7_frontend"
    if not tf_dir.exists():
        print(f"❌ Terraform directory not found: {tf_dir}")
        sys.exit(1)

    print("🔍 Fetching Terraform infrastructure details...")
    outputs_json = run_command(["terraform", "output", "-json"], cwd=tf_dir, capture_output=True)
    outputs = json.loads(outputs_json)

    bucket_name = outputs["s3_bucket_name"]["value"]
    api_url = outputs["api_gateway_url"]["value"]
    cloudfront_url = outputs["cloudfront_url"]["value"]

    print(f"  • S3 Bucket: {bucket_name}")
    print(f"  • CloudFront Domain: {cloudfront_url}")
    print(f"  • Production API URL: {api_url}")

    # 2. Build Frontend
    frontend_dir = Path(__file__).parent.parent / "frontend"
    print("\n📦 Building NextJS frontend for production...")
    build_env = os.environ.copy()
    build_env["NODE_ENV"] = "production"

    # Write .env.production.local
    env_prod_local = frontend_dir / ".env.production.local"
    env_prod = frontend_dir / ".env.production"
    if env_prod.exists():
        lines = env_prod.read_text().splitlines(keepends=True)
    else:
        lines = []

    api_line_found = False
    for i, line in enumerate(lines):
        if line.startswith("NEXT_PUBLIC_API_URL="):
            lines[i] = f"NEXT_PUBLIC_API_URL={api_url}\n"
            api_line_found = True
            break
    if not api_line_found:
        lines.append(f"\nNEXT_PUBLIC_API_URL={api_url}\n")
    env_prod_local.write_text("".join(lines))

    run_command("npm run build" if IS_WINDOWS else ["npm", "run", "build"], cwd=frontend_dir, env=build_env)

    out_dir = frontend_dir / "out"
    if not out_dir.exists():
        print(f"❌ Build output directory not found: {out_dir}")
        sys.exit(1)

    # 3. Upload to S3
    print(f"\n📤 Syncing build files to S3 bucket: s3://{bucket_name}/")
    run_command([
        "aws", "s3", "sync",
        str(out_dir) + "/",
        f"s3://{bucket_name}/",
        "--delete"
    ])

    # 4. Invalidate CloudFront CDN
    print("\n🔄 Invalidating CloudFront cache...")
    domain_clean = cloudfront_url.replace("https://", "").replace("/", "")
    dist_id = run_command([
        "aws", "cloudfront", "list-distributions",
        "--query", f"DistributionList.Items[?DomainName=='{domain_clean}'].Id",
        "--output", "text"
    ], capture_output=True)

    if dist_id and dist_id.strip():
        run_command([
            "aws", "cloudfront", "create-invalidation",
            "--distribution-id", dist_id.strip(),
            "--paths", "/*"
        ])
        print(f"  ✅ CloudFront cache invalidation issued for distribution: {dist_id.strip()}")
    else:
        print("  ⚠️ Could not auto-detect CloudFront Distribution ID. Skipping invalidation.")

    print("\n" + "=" * 50)
    print("✅ Frontend deployment to S3 complete!")
    print(f"🌐 Application URL: {cloudfront_url}\n")


if __name__ == "__main__":
    main()
