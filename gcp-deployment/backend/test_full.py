#!/usr/bin/env python3
"""Full end-to-end test via SQS for the Alex platform"""

import os
import json
import boto3
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(override=True)

from src import Database
from src.schemas import UserCreate, InstrumentCreate, AccountCreate, PositionCreate

def setup_test_data(db):
    """Ensure test user and portfolio exist"""
    print("Setting up test data...")
    
    # Check/create test user
    test_user_id = 'test_user_001'
    user = db.users.find_by_clerk_id(test_user_id)
    if not user:
        user_data = UserCreate(
            clerk_user_id=test_user_id,
            display_name="Test User",
            years_to_retirement=25,
            target_allocation={'stocks': 70, 'bonds': 20, 'alternatives': 10}
        )
        db.users.create(user_data.model_dump())
        print(f"  ✓ Created test user: {test_user_id}")
    else:
        print(f"  ✓ Test user exists: {test_user_id}")
    
    # Check/create test account
    accounts = db.accounts.find_by_user(test_user_id)
    if not accounts:
        account_data = AccountCreate(
            clerk_user_id=test_user_id,
            account_name="Test 401(k)",
            account_type="401k",
            cash_balance=5000.00
        )
        account_id = db.accounts.create(account_data.model_dump())
        print(f"  ✓ Created test account: Test 401(k)")
        
        # Add some positions
        positions = [
            {'symbol': 'SPY', 'quantity': 100},
            {'symbol': 'QQQ', 'quantity': 50},
            {'symbol': 'BND', 'quantity': 200},
            {'symbol': 'VTI', 'quantity': 75}
        ]
        
        for pos in positions:
            position_data = PositionCreate(
                account_id=account_id,
                symbol=pos['symbol'],
                quantity=pos['quantity']
            )
            db.positions.create(position_data.model_dump())
        print(f"  ✓ Created {len(positions)} positions")
    else:
        print(f"  ✓ Test account exists with {len(db.positions.find_by_account(accounts[0]['id']))} positions")
    
    return test_user_id

def main():
    print("=" * 70)
    print("🎯 Full End-to-End Test via SQS")
    print("=" * 70)
    
    db = Database()
    sqs = boto3.client('sqs')
    
    # Setup test data
    test_user_id = setup_test_data(db)
    
    # Create test job
    print("\nCreating analysis job...")
    job_data = {
        'clerk_user_id': test_user_id,
        'job_type': 'portfolio_analysis',
        'status': 'pending',
        'request_payload': {
            'analysis_type': 'full',
            'requested_at': datetime.now(timezone.utc).isoformat(),
            'test_run': True,
            'include_retirement': True,
            'include_charts': True,
            'include_report': True
        }
    }
    
    job_id = db.jobs.create(job_data)
    print(f"  ✓ Created job: {job_id}")
    
    # Get queue URL
    QUEUE_NAME = 'alex-analysis-jobs'
    response = sqs.list_queues(QueueNamePrefix=QUEUE_NAME)
    queue_url = None
    for url in response.get('QueueUrls', []):
        if QUEUE_NAME in url:
            queue_url = url
            break
    
    if not queue_url:
        print(f"  ❌ Queue {QUEUE_NAME} not found")
        return 1
    
    print(f"  ✓ Found queue: {QUEUE_NAME}")
    
    # Send message to SQS
    print("\nTriggering analysis via SQS...")
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({'job_id': job_id})
    )
    print(f"  ✓ Message sent: {response['MessageId']}")
    
    # Monitor job progress
    print("\n⏳ Monitoring job progress...")
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
            
            if status == 'failed' and job.get('error_message'):
                print(f"       Error: {job.get('error_message')}")
        
        if status == 'completed':
            print("-" * 50)
            print("\n✅ Job completed successfully!")
            print("\n📊 Analysis Results:")
            
            # Report
            if job.get('report_payload'):
                report_content = job['report_payload'].get('content', '')
                print(f"\n📝 Report Generated:")
                print(f"   - Length: {len(report_content)} characters")
                print(f"   - Preview: {report_content[:200]}...")
            else:
                print("\n❌ No report found")
            
            # Charts
            if job.get('charts_payload'):
                charts = job['charts_payload']
                print(f"\n📊 Charts Created: {len(charts)} visualizations")
                for chart_key, chart_data in charts.items():
                    if isinstance(chart_data, dict):
                        title = chart_data.get('title', 'Untitled')
                        chart_type = chart_data.get('type', 'unknown')
                        data_points = len(chart_data.get('data', []))
                        print(f"   - {chart_key}: {title} ({chart_type}, {data_points} data points)")
            else:
                print("\n❌ No charts found")
            
            # Retirement
            if job.get('retirement_payload'):
                retirement = job['retirement_payload']
                print(f"\n🎯 Retirement Analysis:")
                if isinstance(retirement, dict):
                    if 'success_rate' in retirement:
                        print(f"   - Success Rate: {retirement['success_rate']}%")
                    if 'projected_balance' in retirement:
                        print(f"   - Projected Balance: ${retirement['projected_balance']:,.0f}")
                    if 'analysis' in retirement:
                        print(f"   - Analysis Length: {len(retirement['analysis'])} characters")
            else:
                print("\n❌ No retirement analysis found")
            
            # Summary
            if job.get('summary_payload'):
                summary = job['summary_payload']
                print(f"\n📋 Summary:")
                if isinstance(summary, dict):
                    for key, value in summary.items():
                        if key != 'timestamp':
                            print(f"   - {key}: {value}")
            
            break
        elif status == 'failed':
            print("-" * 50)
            print(f"\n❌ Job failed")
            if job.get('error_message'):
                print(f"Error details: {job['error_message']}")
            break
        
        time.sleep(2)
    else:
        print("-" * 50)
        print("\n❌ Job timed out after 3 minutes")
        print(f"Final status: {job['status']}")
        return 1
    
    print(f"\n📋 Job Details:")
    print(f"   - Job ID: {job_id}")
    print(f"   - User ID: {test_user_id}")
    print(f"   - Total Time: {int(time.time() - start_time)} seconds")
    
    return 0

if __name__ == "__main__":
    exit(main())