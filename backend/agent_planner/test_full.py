#!/usr/bin/env python3
"""
Run a full end-to-end test of the Agent Planner orchestration.
This creates a test job and calls the agent directly with Bedrock.

Usage:
    cd backend/agent_planner
    uv run test_full.py
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
from src.schemas import JobCreate

db = Database()


def create_test_job():
    """Create a test job for orchestration."""
    
    # Create test user
    test_user_id = "test_user_full_agent_planner"
    
    try:
        # Try to create user
        user_data = {
            "clerk_user_id": test_user_id,
            "display_name": "Test User Agent Planner Full",
            "years_until_retirement": 25,
            "target_retirement_income": 75000
        }
        db.users.create_user(**user_data)
        print(f"✓ Created test user: {test_user_id}")
    except Exception as e:
        print(f"ℹ️  User might already exist: {e}")
    
    # Create test account and positions
    try:
        # Create account
        account_data = {
            "clerk_user_id": test_user_id,
            "account_name": "Test Investment Account", 
            "account_type": "investment",
            "cash_balance": 10000.0
        }
        account_id = db.accounts.create(**account_data)
        print(f"✓ Created test account: {account_id}")
        
        # Create test positions
        test_positions = [
            {"symbol": "SPY", "quantity": 50.0},
            {"symbol": "BND", "quantity": 100.0}, 
            {"symbol": "VTI", "quantity": 25.0},
            {"symbol": "VXUS", "quantity": 30.0},
            {"symbol": "QQQ", "quantity": 15.0}
        ]
        
        for pos in test_positions:
            db.positions.create(account_id=account_id, **pos)
            print(f"✓ Created position: {pos['symbol']}")
            
    except Exception as e:
        print(f"ℹ️  Test data might already exist: {e}")
    
    # Create job
    job_create = JobCreate(
        clerk_user_id=test_user_id,
        job_type="portfolio_analysis", 
        request_payload={"analysis_type": "comprehensive", "test": True}
    )
    
    job_id = db.jobs.create(job_create.model_dump())
    print(f"✓ Created test job: {job_id}")
    
    return job_id, test_user_id


def main():
    """Run the full test."""
    
    print("🚀 Agent Planner Full Test")
    print("=" * 70)
    
    # Create test job
    print("\n📋 Setting up test data...")
    try:
        job_id, test_user_id = create_test_job()
    except Exception as e:
        print(f"❌ Failed to create test job: {e}")
        return 1
    
    # Test the agent directly
    print(f"\n🤖 Testing Agent Planner directly...")
    print(f"Job ID: {job_id}")
    print("-" * 50)
    
    try:
        # Import and test the agent
        from agent import planner_agent
        
        test_payload = {
            "job_id": job_id
        }
        
        start_time = time.time()
        result = planner_agent(test_payload)
        elapsed_time = time.time() - start_time
        
        print(f"⏱️  Agent execution time: {elapsed_time:.2f} seconds")
        print(f"📤 Status Code: {result['statusCode']}")
        
        if result['statusCode'] == 200:
            body = json.loads(result['body'])
            print(f"✅ Success: {body.get('success', False)}")
            print(f"📝 Message: {body.get('message', 'N/A')}")
            
            # Show output preview
            final_output = body.get('final_output', '')
            if final_output:
                print(f"\n📊 Output Preview ({len(final_output)} chars):")
                print("-" * 50)
                preview = final_output[:500]
                if len(final_output) > 500:
                    preview += "..."
                print(preview)
            
        else:
            body = json.loads(result['body'])
            print(f"❌ Error: {body.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        print(f"❌ Agent test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Check job status in database
    print(f"\n📋 Checking final job status...")
    try:
        job = db.jobs.find_by_id(job_id)
        print(f"📊 Job Status: {job['status']}")
        
        if job.get('error_message'):
            print(f"⚠️  Error Message: {job['error_message']}")
            
        # Display any results that were saved
        if job.get('report_payload'):
            print(f"📝 Report saved: {len(str(job['report_payload']))} chars")
            
        if job.get('charts_payload'):
            print(f"📊 Charts saved: {len(job['charts_payload'])} items")
            
        if job.get('retirement_payload'):
            print(f"🎯 Retirement analysis saved")
            
    except Exception as e:
        print(f"⚠️  Could not check job status: {e}")
    
    # Clean up
    print(f"\n🧹 Cleaning up test data...")
    try:
        # Delete test job
        db.jobs.delete(job_id)
        print(f"✓ Deleted test job: {job_id}")
        
        # Delete test user and related data
        db.client.delete("users", "clerk_user_id = :clerk_id", {"clerk_id": test_user_id})
        print(f"✓ Deleted test user: {test_user_id}")
        
    except Exception as e:
        print(f"⚠️  Cleanup failed: {e}")
    
    print("\n" + "=" * 70)
    print("✅ Full Agent Planner test completed!")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    exit(main())