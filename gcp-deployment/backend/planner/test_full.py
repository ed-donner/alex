#!/usr/bin/env python3
"""
Run a full end-to-end test of the Alex agent orchestration.
This creates a test job and monitors it through completion.

Usage:
    cd backend/planner
    uv run run_full_test.py
"""

import os
import json
import boto3
import time
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import database
from src import Database

db = Database()
sqs = boto3.client('sqs')
sts = boto3.client('sts')

# Get configuration
QUEUE_NAME = os.getenv('SQS_QUEUE_NAME', 'alex-analysis-jobs')


def get_queue_url():
    """Get the SQS queue URL."""
    response = sqs.list_queues(QueueNamePrefix=QUEUE_NAME)
    queues = response.get('QueueUrls', [])
    
    for queue_url in queues:
        if QUEUE_NAME in queue_url:
            return queue_url
    
    raise ValueError(f"Queue {QUEUE_NAME} not found")


def main():
    """Run the full test."""
    print("=" * 70)
    print("🎯 Alex Agent Orchestration - Full Test")
    print("=" * 70)
    
    # Display AWS info
    account_id = sts.get_caller_identity()['Account']
    region = boto3.Session().region_name
    print(f"AWS Account: {account_id}")
    print(f"AWS Region: {region}")
    print(f"Bedrock Region: {os.getenv('BEDROCK_REGION', 'us-west-2')}")
    print(f"Bedrock Model: {os.getenv('BEDROCK_MODEL_ID', 'Not set')}")
    print()
    
    # Check for test user
    print("📊 Checking test data...")
    test_user_id = 'test_user_001'
    user = db.users.find_by_clerk_id(test_user_id)
    
    if not user:
        print("❌ Test user not found. Please run database setup first:")
        print("   cd ../database && uv run reset_db.py --with-test-data")
        return 1
    
    print(f"✓ Test user: {user.get('display_name', test_user_id)}")
    
    # Check accounts and positions
    accounts = db.accounts.find_by_user(test_user_id)
    total_positions = 0
    for account in accounts:
        positions = db.positions.find_by_account(account['id'])
        total_positions += len(positions)
    
    print(f"✓ Portfolio: {len(accounts)} accounts, {total_positions} positions")
    
    # Create test job
    print("\n🚀 Creating test job...")
    job_data = {
        'clerk_user_id': test_user_id,
        'job_type': 'portfolio_analysis',
        'status': 'pending',
        'request_payload': {
            'analysis_type': 'full',
            'requested_at': datetime.now(timezone.utc).isoformat(),
            'test_run': True
        }
    }
    
    job_id = db.jobs.create(job_data)
    print(f"✓ Created job: {job_id}")
    
    # Send to SQS
    print("\n📤 Sending job to SQS queue...")
    try:
        queue_url = get_queue_url()
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({'job_id': job_id})
        )
        print(f"✓ Message sent: {response['MessageId']}")
    except Exception as e:
        print(f"❌ Failed to send to SQS: {e}")
        return 1
    
    # Monitor job
    print("\n⏳ Monitoring job progress (timeout: 3 minutes)...")
    print("-" * 50)
    
    start_time = time.time()
    timeout = 180  # 3 minutes
    last_status = None
    
    while time.time() - start_time < timeout:
        job = db.jobs.find_by_id(job_id)
        status = job['status']
        
        if status != last_status:
            elapsed = int(time.time() - start_time)
            print(f"[{elapsed:3d}s] Status: {status}")
            last_status = status
        
        if status == 'completed':
            print("-" * 50)
            print("✅ Job completed successfully!")
            break
        elif status == 'failed':
            print("-" * 50)
            print(f"❌ Job failed: {job.get('error_message', 'Unknown error')}")
            return 1
        
        time.sleep(2)
    else:
        print("-" * 50)
        print("❌ Job timed out after 3 minutes")
        return 1
    
    # Display results
    print("\n" + "=" * 70)
    print("📋 ANALYSIS RESULTS")
    print("=" * 70)
    
    # Orchestrator summary
    if job.get('summary_payload'):
        print("\n🎯 Orchestrator Summary:")
        summary = job['summary_payload']
        print(f"Summary: {summary.get('summary', 'N/A')}")
        
        if summary.get('key_findings'):
            print("\nKey Findings:")
            for finding in summary['key_findings']:
                print(f"  • {finding}")
        
        if summary.get('recommendations'):
            print("\nRecommendations:")
            for rec in summary['recommendations']:
                print(f"  • {rec}")
    
    # Report analysis
    if job.get('report_payload'):
        print("\n📝 Portfolio Report:")
        report = job['report_payload']
        analysis = report.get('analysis', '')
        print(f"  Length: {len(analysis)} characters")
        if analysis:
            preview = analysis[:300]
            if len(analysis) > 300:
                preview += "..."
            print(f"  Preview: {preview}")
    
    # Charts
    if job.get('charts_payload'):
        print(f"\n📊 Visualizations: {len(job['charts_payload'])} charts")
        for chart_key, chart_data in job['charts_payload'].items():
            print(f"  • {chart_key}: {chart_data.get('title', 'Untitled')}")
            if chart_data.get('data'):
                print(f"    Data points: {len(chart_data['data'])}")
    
    # Retirement projections
    if job.get('retirement_payload'):
        print("\n🎯 Retirement Analysis:")
        ret = job['retirement_payload']
        print(f"  Success Rate: {ret.get('success_rate', 'N/A')}%")
        print(f"  Projected Value: ${ret.get('projected_value', 0):,.0f}")
        print(f"  Years to Retirement: {ret.get('years_to_retirement', 'N/A')}")
    
    print("\n" + "=" * 70)
    print("✅ Full test completed successfully!")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    exit(main())