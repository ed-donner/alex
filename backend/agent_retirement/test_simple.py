#!/usr/bin/env python3
"""
Simple test for Agent Retirement
"""

import json
from dotenv import load_dotenv

load_dotenv(override=True)

from src import Database
from src.schemas import JobCreate
from agent import retirement_agent

def test_retirement():
    """Test the agent retirement with simple portfolio data"""
    
    # Create a real user and job in the database
    db = Database()
    
    # Create test user first
    test_user_id = "test_user_retirement_001"
    try:
        db.users.create_user(
            clerk_user_id=test_user_id,
            display_name="Test User Retirement",
            years_until_retirement=25,
            target_retirement_income=75000
        )
        print(f"Created test user: {test_user_id}")
    except Exception as e:
        print(f"User might already exist: {e}")
    
    # Create test job
    job_create = JobCreate(
        clerk_user_id=test_user_id,
        job_type="portfolio_analysis",
        request_payload={"test": True}
    )
    job_id = db.jobs.create(job_create.model_dump())
    print(f"Created test job: {job_id}")
    
    test_payload = {
        "job_id": job_id,
        "portfolio_data": {
            "accounts": [
                {
                    "name": "401(k)",
                    "type": "retirement",
                    "cash_balance": 10000,
                    "positions": [
                        {
                            "symbol": "SPY",
                            "quantity": 100,
                            "instrument": {
                                "name": "SPDR S&P 500 ETF",
                                "current_price": 450,
                                "allocation_asset_class": {"equity": 100.0}
                            }
                        },
                        {
                            "symbol": "BND",
                            "quantity": 100,
                            "instrument": {
                                "name": "Vanguard Total Bond Market ETF",
                                "current_price": 75,
                                "allocation_asset_class": {"fixed_income": 100.0}
                            }
                        }
                    ]
                }
            ]
        }
    }
    
    print("Testing Agent Retirement...")
    print("=" * 60)
    
    result = retirement_agent(test_payload)
    
    print(f"Status Code: {result['statusCode']}")
    
    if result['statusCode'] == 200:
        body = json.loads(result['body'])
        print(f"Success: {body.get('success', False)}")
        print(f"Message: {body.get('message', 'N/A')}")
        
        # Check what was actually saved in the database
        print("\n" + "=" * 60)
        print("CHECKING DATABASE CONTENT")
        print("=" * 60)
        
        job = db.jobs.find_by_id(job_id)
        if job and job.get('retirement_payload'):
            payload = job['retirement_payload']
            print(f"✅ Retirement analysis data found in database")
            print(f"Payload keys: {list(payload.keys())}")
            
            if 'analysis' in payload:
                content = payload['analysis']
                print(f"\nContent type: {type(content).__name__}")
                
                if isinstance(content, str):
                    print(f"Analysis length: {len(content)} characters")
                    
                    # Check if it contains reasoning artifacts
                    reasoning_indicators = [
                        "I need to",
                        "I will",
                        "Let me",
                        "First,",
                        "I should",
                        "I'll",
                        "Now I",
                        "Next,",
                    ]
                    
                    contains_reasoning = any(indicator.lower() in content.lower() for indicator in reasoning_indicators)
                    
                    if contains_reasoning:
                        print("⚠️  WARNING: Analysis may contain reasoning/thinking text")
                    else:
                        print("✅ Analysis appears to be final output only (no reasoning detected)")
                    
                    # Show first 500 characters and last 200 characters
                    print(f"\nFirst 500 characters:")
                    print("-" * 40)
                    print(content[:500])
                    print("-" * 40)
                    
                    if len(content) > 700:
                        print(f"\nLast 200 characters:")
                        print("-" * 40)
                        print(content[-200:])
                        print("-" * 40)
                else:
                    print(f"⚠️  Content is not a string: {type(content)}")
                    print(f"Content: {str(content)[:200]}")
            
            print(f"\nGenerated at: {payload.get('generated_at', 'N/A')}")
            print(f"Agent: {payload.get('agent', 'N/A')}")
        else:
            print("❌ No retirement analysis data found in database")
    else:
        print(f"Error: {result['body']}")
    
    # Clean up - delete the test job and user
    try:
        db.jobs.delete(job_id)
        print(f"\n🧹 Deleted test job: {job_id}")
    except Exception as e:
        print(f"⚠️  Failed to delete test job: {e}")
    
    try:
        # Delete user using clerk_user_id
        db.client.delete("users", "clerk_user_id = :clerk_id", {"clerk_id": test_user_id})
        print(f"🧹 Deleted test user: {test_user_id}")
    except Exception as e:
        print(f"⚠️  Failed to delete test user: {e}")
    
    print("=" * 60)

if __name__ == "__main__":
    test_retirement()