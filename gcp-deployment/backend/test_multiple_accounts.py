#!/usr/bin/env python3
"""
Test that the system correctly handles users with multiple accounts.
"""

import json
import time
import uuid
import boto3
import os
from decimal import Decimal
from dotenv import load_dotenv

from src import Database

# Load environment variables
load_dotenv(override=True)

def test_multiple_accounts():
    """Test analysis for a user with multiple accounts"""
    
    print("=" * 70)
    print("🎯 Multiple Accounts Test")
    print("=" * 70)
    
    # Initialize database
    db = Database()
    
    # Create test user
    test_user_id = f'test_multi_{uuid.uuid4().hex[:8]}'
    user_id = db.users.create_user(
        clerk_user_id=test_user_id,
        display_name='Multi Account Test User',
        years_until_retirement=25,
        target_retirement_income=Decimal('150000')
    )
    print(f'\n✅ Created test user: {test_user_id}')
    
    # Ensure instruments exist
    instruments = ["SPY", "BND", "VTI", "VXUS", "QQQ", "IWM", "EFA", "AGG", "VNQ", "GLD"]
    for i, symbol in enumerate(instruments):
        existing = db.instruments.find_by_symbol(symbol)
        if not existing:
            db.instruments.create({
                "symbol": symbol,
                "name": f"Test ETF {symbol}",
                "instrument_type": "etf",
                "current_price": 100.0 + i * 50,
                "allocation_asset_class": {"equity": 100.0} if i % 2 == 0 else {"fixed_income": 100.0},
                "allocation_regions": {"north_america": 100.0},
                "allocation_sectors": {"other": 100.0}
            }, returning='symbol')
            print(f'✅ Created instrument: {symbol}')
    # Create multiple accounts with different portfolios
    accounts = []
    
    # Account 1: Taxable Brokerage
    account1_id = db.accounts.create_account(
        clerk_user_id=test_user_id,
        account_name='Taxable Brokerage',
        account_purpose='taxable_brokerage',
        cash_balance=Decimal('5000.0')
    )
    accounts.append(account1_id)
    print(f'✅ Created account 1: Taxable Brokerage')
    
    # Add positions to account 1
    positions1 = [
        ('SPY', 100),
        ('QQQ', 50),
        ('BND', 200)
    ]
    for symbol, quantity in positions1:
        sql = "INSERT INTO positions (account_id, symbol, quantity) VALUES (:account_id::uuid, :symbol, :quantity)"
        params = [
            {'name': 'account_id', 'value': {'stringValue': account1_id}},
            {'name': 'symbol', 'value': {'stringValue': symbol}},
            {'name': 'quantity', 'value': {'longValue': quantity}}
        ]
        db.client.execute(sql, params)
    print(f'  Added {len(positions1)} positions')
    
    # Account 2: Roth IRA
    account2_id = db.accounts.create_account(
        clerk_user_id=test_user_id,
        account_name='Roth IRA',
        account_purpose='roth_ira',
        cash_balance=Decimal('2000.0')
    )
    accounts.append(account2_id)
    print(f'✅ Created account 2: Roth IRA')
    
    # Add positions to account 2
    positions2 = [
        ('VTI', 75),
        ('VXUS', 50),
        ('GLD', 25)
    ]
    for symbol, quantity in positions2:
        sql = "INSERT INTO positions (account_id, symbol, quantity) VALUES (:account_id::uuid, :symbol, :quantity)"
        params = [
            {'name': 'account_id', 'value': {'stringValue': account2_id}},
            {'name': 'symbol', 'value': {'stringValue': symbol}},
            {'name': 'quantity', 'value': {'longValue': quantity}}
        ]
        db.client.execute(sql, params)
    print(f'  Added {len(positions2)} positions')
    
    # Account 3: 401(k)
    account3_id = db.accounts.create_account(
        clerk_user_id=test_user_id,
        account_name='401(k)',
        account_purpose='401k',
        cash_balance=Decimal('10000.0')
    )
    accounts.append(account3_id)
    print(f'✅ Created account 3: 401(k)')
    
    # Add positions to account 3
    positions3 = [
        ('VEA', 150),
        ('TSLA', 10),
        ('ARKK', 50),
        ('BND', 300)
    ]
    for symbol, quantity in positions3:
        sql = "INSERT INTO positions (account_id, symbol, quantity) VALUES (:account_id::uuid, :symbol, :quantity)"
        params = [
            {'name': 'account_id', 'value': {'stringValue': account3_id}},
            {'name': 'symbol', 'value': {'stringValue': symbol}},
            {'name': 'quantity', 'value': {'longValue': quantity}}
        ]
        db.client.execute(sql, params)
    print(f'  Added {len(positions3)} positions')
    
    print(f'\n📊 Total: 3 accounts, {len(positions1) + len(positions2) + len(positions3)} positions')
    
    # Create a job
    job_id = db.jobs.create_job(test_user_id, "portfolio_analysis")
    print(f'\n🚀 Created job: {job_id}')
    
    # Trigger analysis via SQS
    """Send a job to SQS"""
    sqs = boto3.client('sqs', region_name=os.getenv('DEFAULT_AWS_REGION', 'us-east-1'))
    
    # Get queue URL
    queue_name = 'alex-analysis-jobs'
    response = sqs.get_queue_url(QueueName=queue_name)
    queue_url = response['QueueUrl']

    # sqs = boto3.client('sqs', region_name='ap-southeast-2')
    # queue_url = 'https://sqs.ap-southeast-2.amazonaws.com/596644540428/alex-analysis-jobs'
    
    message = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({'job_id': job_id})
    )
    print(f'📤 Sent message to SQS: {message["MessageId"]}')
    
    print('\n⏳ Monitoring job progress...')
    print('-' * 50)
    
    # Monitor job
    start_time = time.time()
    for i in range(90):  # Max 3 minutes
        time.sleep(2)
        job_status = db.jobs.find_by_id(job_id)
        status = job_status.get('status', 'unknown') if job_status else 'unknown'
        elapsed = int(time.time() - start_time)
        print(f'[{elapsed:3}s] Status: {status}')
        if status in ['completed', 'failed']:
            break
    
    print('-' * 50)
    
    # Check results
    success = status == 'completed'
    
    if success:
        print('\n✅ Job completed successfully!')
        
        # Check that all accounts were analyzed
        print('\n📋 ANALYSIS RESULTS:')
        
        if job_status.get('summary_payload'):
            summary = job_status['summary_payload']
            print(f'\n🎯 Summary:')
            print(f'  {summary.get("summary", "N/A")[:300]}...')
            
            # Check key findings mention multiple accounts
            findings = summary.get('key_findings', [])
            if findings:
                print(f'\n📊 Key Findings ({len(findings)}):')
                for finding in findings[:3]:
                    print(f'  • {finding}')
        
        if job_status.get('report_payload'):
            report = job_status['report_payload']
            content = report.get('content', '')
            # Check that report mentions all 3 accounts
            accounts_mentioned = all([
                'Taxable Brokerage' in content or 'taxable' in content.lower(),
                'Roth IRA' in content or 'roth' in content.lower(),
                '401(k)' in content or '401k' in content.lower()
            ])
            print(f'\n📝 Report:')
            print(f'  Length: {len(content)} characters')
            print(f'  All accounts analyzed: {"✅ YES" if accounts_mentioned else "❌ NO"}')
            
            if not accounts_mentioned:
                print('  ⚠️  Warning: Not all accounts appear in the report')
        
        if job_status.get('charts_payload'):
            charts = job_status['charts_payload']
            print(f'\n📊 Charts: {len(charts)} visualizations created')
            
            # Check for account-related charts
            has_account_chart = any('account' in str(chart).lower() for chart in charts.values())
            print(f'  Account distribution chart: {"✅ YES" if has_account_chart else "❌ NO"}')
        
        if job_status.get('retirement_payload'):
            print(f'\n🎯 Retirement Analysis: ✅ Generated')
    else:
        print(f'\n❌ Job failed with status: {status}')
        if job_status.get('error'):
            print(f'Error: {job_status["error"]}')
    
    # Clean up
    print(f'\n🧹 Cleaning up test data...')
    try:
        # Delete job
        sql = "DELETE FROM jobs WHERE id = :job_id::uuid"
        params = [{'name': 'job_id', 'value': {'stringValue': job_id}}]
        db.client.execute(sql, params)
        
        # Delete positions
        for account_id in accounts:
            sql = "DELETE FROM positions WHERE account_id = :account_id::uuid"
            params = [{'name': 'account_id', 'value': {'stringValue': account_id}}]
            db.client.execute(sql, params)
        
        # Delete accounts
        sql = "DELETE FROM accounts WHERE clerk_user_id = :user_id"
        params = [{'name': 'user_id', 'value': {'stringValue': test_user_id}}]
        db.client.execute(sql, params)
        
        # Delete user
        sql = "DELETE FROM users WHERE clerk_user_id = :user_id"
        params = [{'name': 'user_id', 'value': {'stringValue': test_user_id}}]
        db.client.execute(sql, params)
        
        print('✅ Test data cleaned up successfully')
    except Exception as e:
        print(f'⚠️  Warning: Cleanup failed: {e}')
    
    print('\n' + '=' * 70)
    print(f'✅ Multiple accounts test {"PASSED" if success else "FAILED"}!')
    print('=' * 70)
    
    return success


if __name__ == '__main__':
    success = test_multiple_accounts()
    exit(0 if success else 1)
