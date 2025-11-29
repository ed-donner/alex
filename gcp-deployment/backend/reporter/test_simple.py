#!/usr/bin/env python3
"""
Simple test for Reporter agent
"""

import asyncio
import json
from dotenv import load_dotenv

load_dotenv(override=True)

from src import Database
from src.schemas import JobCreate
from lambda_handler import lambda_handler

def test_reporter():
    """Test the reporter agent with simple portfolio data"""
    
    # Create a real job in the database
    db = Database()
    job_create = JobCreate(
        clerk_user_id="test_user_001",
        job_type="portfolio_analysis",
        request_payload={"test": True}
    )
    job_id = db.jobs.create(job_create.model_dump())
    print(f"Created test job: {job_id}")
    
    test_event = {
        "job_id": job_id,
        "portfolio_data": {
            "accounts": [
                {
                    "name": "401(k)",
                    "cash_balance": 5000,
                    "positions": [
                        {
                            "symbol": "SPY",
                            "quantity": 100,
                            "instrument": {
                                "name": "SPDR S&P 500 ETF",
                                "current_price": 450,
                                "asset_class": "equity"
                            }
                        }
                    ]
                }
            ]
        },
        "user_data": {
            "years_until_retirement": 25,
            "target_retirement_income": 75000
        }
    }
    
    print("Testing Reporter Agent...")
    print("=" * 60)
    
    result = lambda_handler(test_event, None)
    
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
        if job and job.get('report_payload'):
            payload = job['report_payload']
            print(f"✅ Report data found in database")
            print(f"Payload keys: {list(payload.keys())}")
            
            if 'content' in payload:
                content = payload['content']
                print(f"\nContent type: {type(content).__name__}")
                
                if isinstance(content, str):
                    print(f"Report length: {len(content)} characters")
                    
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
                        print("⚠️  WARNING: Report may contain reasoning/thinking text")
                    else:
                        print("✅ Report appears to be final output only (no reasoning detected)")
                    
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
            print("❌ No report data found in database")
    else:
        print(f"Error: {result['body']}")
    
    # Clean up - delete the test job
    db.jobs.delete(job_id)
    print(f"\nDeleted test job: {job_id}")
    
    print("=" * 60)

if __name__ == "__main__":
    test_reporter()