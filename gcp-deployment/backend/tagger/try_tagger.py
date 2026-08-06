#!/usr/bin/env python3
"""
Complete test for Tagger: package, deploy, and test
"""

import os
import sys
import json
import time
import subprocess
import boto3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

from src import Database

class TaggerTest:
    """Test class that packages, deploys, and tests the tagger Lambda"""

    def __init__(self):
        self.lambda_client = boto3.client('lambda', region_name='us-east-1')
        self.db = Database()

    def package_tagger(self):
        """Package the tagger Lambda using Docker"""
        print("\n📦 Packaging Tagger Lambda...")
        print("=" * 60)

        try:
            # Run package_docker.py
            result = subprocess.run(
                ['uv', 'run', 'package_docker.py'],
                cwd=Path(__file__).parent,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print(f"❌ Packaging failed: {result.stderr}")
                return False

            # Check if zip file was created
            zip_path = Path(__file__).parent / 'tagger_lambda.zip'
            if zip_path.exists():
                size_mb = zip_path.stat().st_size / (1024 * 1024)
                print(f"✅ Package created: {zip_path} ({size_mb:.1f} MB)")
                return True
            else:
                print("❌ Package file not found")
                return False

        except Exception as e:
            print(f"❌ Error packaging: {e}")
            return False

    def deploy_tagger(self):
        """Deploy the tagger Lambda to AWS"""
        print("\n🚀 Deploying Tagger Lambda...")
        print("=" * 60)

        try:
            # Package is too large for direct upload, must use S3
            s3_client = boto3.client('s3', region_name='us-east-1')

            # Use the existing Lambda packages bucket
            bucket_name = f"alex-lambda-packages-{boto3.client('sts').get_caller_identity()['Account']}"
            key = 'tagger/tagger_lambda.zip'

            print(f"Uploading to S3 bucket: {bucket_name}")
            zip_path = Path(__file__).parent / 'tagger_lambda.zip'

            # Upload to S3
            with open(zip_path, 'rb') as f:
                s3_client.upload_fileobj(f, bucket_name, key)

            print(f"✅ Uploaded to S3: s3://{bucket_name}/{key}")

            # Update Lambda function code from S3
            print("Updating Lambda function from S3...")
            response = self.lambda_client.update_function_code(
                FunctionName='alex-tagger',
                S3Bucket=bucket_name,
                S3Key=key
            )

            # Wait for Lambda to be updated
            print("Waiting for Lambda to be ready...")
            waiter = self.lambda_client.get_waiter('function_updated')
            waiter.wait(FunctionName='alex-tagger')

            print(f"✅ Lambda deployed successfully")
            print(f"   Last modified: {response['LastModified']}")
            print(f"   Code size: {response['CodeSize'] / (1024*1024):.1f} MB")
            return True

        except Exception as e:
            print(f"❌ Error deploying: {e}")
            return False

    def test_tagger(self):
        """Test the deployed tagger Lambda"""
        print("\n🧪 Testing Tagger Lambda...")
        print("=" * 60)

        # Test instruments - mix of ETFs and stocks
        test_instruments = [
            {"symbol": "ARKK", "name": "ARK Innovation ETF", "instrument_type": "etf"},
            {"symbol": "SOFI", "name": "SoFi Technologies Inc", "instrument_type": "stock"},
            {"symbol": "TSLA", "name": "Tesla Inc", "instrument_type": "stock"},
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "instrument_type": "etf"}
        ]

        print(f"Testing with {len(test_instruments)} instruments:")
        for inst in test_instruments:
            print(f"  - {inst['symbol']}: {inst['name']}")

        try:
            # Invoke Lambda
            print("\nInvoking Lambda function...")
            start_time = time.time()

            response = self.lambda_client.invoke(
                FunctionName='alex-tagger',
                InvocationType='RequestResponse',
                Payload=json.dumps({'instruments': test_instruments})
            )

            elapsed = time.time() - start_time

            # Parse response
            result = json.loads(response['Payload'].read())

            if response['StatusCode'] == 200:
                print(f"✅ Lambda executed successfully in {elapsed:.1f} seconds")

                # Parse the body if it's a string
                if isinstance(result.get('body'), str):
                    body = json.loads(result['body'])
                else:
                    body = result.get('body', result)

                print(f"\n📊 Results:")
                print(f"  Tagged: {body.get('tagged', 0)} instruments")
                print(f"  Updated: {body.get('updated', [])}")
                if body.get('errors'):
                    print(f"  Errors: {body.get('errors')}")

                # Show classifications
                if body.get('classifications'):
                    print(f"\n📈 Classifications:")
                    for cls in body['classifications']:
                        print(f"\n  {cls['symbol']} ({cls['type']}):")
                        print(f"    Asset Class: {cls.get('asset_class', {})}")
                        print(f"    Regions: {cls.get('regions', {})}")
                        print(f"    Sectors: {cls.get('sectors', {})}")

                # Verify in database
                print(f"\n🔍 Verifying in database:")
                for inst in test_instruments:
                    db_inst = self.db.instruments.find_by_symbol(inst['symbol'])
                    if db_inst and db_inst.get('allocation_asset_class'):
                        print(f"  ✅ {inst['symbol']}: Has allocations in database")
                    else:
                        print(f"  ⚠️  {inst['symbol']}: No allocations in database")

            else:
                print(f"❌ Lambda failed with status {response['StatusCode']}")
                print(f"   Response: {result}")

        except Exception as e:
            print(f"❌ Error testing Lambda: {e}")
            import traceback
            traceback.print_exc()

    def run_all(self):
        """Run the complete test: package, deploy, and test"""
        print("\n" + "=" * 60)
        print("🎯 Complete Tagger Test: Package, Deploy, and Test")
        print("=" * 60)

        # Step 1: Package
        if not self.package_tagger():
            print("\n❌ Packaging failed, stopping test")
            return False

        # Step 2: Deploy
        if not self.deploy_tagger():
            print("\n❌ Deployment failed, stopping test")
            return False

        # Give Lambda a moment to stabilize after deployment
        print("\n⏳ Waiting 5 seconds for Lambda to stabilize...")
        time.sleep(5)

        # Step 3: Test
        self.test_tagger()

        print("\n" + "=" * 60)
        print("✅ Complete test finished!")
        print("=" * 60)

        # Reminder about Langfuse
        print("\n💡 Check your Langfuse dashboard for traces:")
        print("   https://us.cloud.langfuse.com")

        return True

def main():
    """Main entry point"""
    tester = TaggerTest()
    tester.run_all()

if __name__ == "__main__":
    main()