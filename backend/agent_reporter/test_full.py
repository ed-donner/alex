"""
Full test for the agent_reporter with actual Bedrock calls
"""

import os
import json
import asyncio
import uuid
from dotenv import load_dotenv

load_dotenv(override=True)

async def test_full():
    """Test the reporter agent with actual Bedrock calls"""
    
    # Import database to create a real job
    from src import Database
    from src.schemas import JobCreate
    
    # Create a real user and job in the database
    db = Database()
    
    # Create test user first
    test_user_id = "test_user_full_001"
    try:
        db.users.create_user(
            clerk_user_id=test_user_id,
            display_name="Test User Full",
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
    test_job_id = db.jobs.create(job_create.model_dump())
    print(f"Created test job in database: {test_job_id}")
    
    # Test payload with realistic data
    payload = {
        "job_id": test_job_id,
        "portfolio_data": {
            "accounts": [
                {
                    "name": "Investment Account",
                    "cash_balance": 10000,
                    "positions": [
                        {
                            "symbol": "SPY",
                            "quantity": 50,
                            "instrument": {
                                "name": "SPDR S&P 500 ETF",
                                "current_price": 450,
                                "allocation_asset_class": {"equity": 100.0},
                                "allocation_regions": {"north_america": 100.0},
                                "allocation_sectors": {
                                    "technology": 28.5,
                                    "healthcare": 14.2,
                                    "financials": 13.1,
                                    "consumer_discretionary": 10.8,
                                    "other": 33.4
                                }
                            },
                        },
                        {
                            "symbol": "BND",
                            "quantity": 100,
                            "instrument": {
                                "name": "Vanguard Total Bond Market ETF",
                                "current_price": 85,
                                "allocation_asset_class": {"fixed_income": 100.0},
                                "allocation_regions": {"north_america": 100.0},
                                "allocation_sectors": {
                                    "treasury": 40.0,
                                    "corporate": 35.0,
                                    "mortgage": 25.0
                                }
                            },
                        }
                    ],
                }
            ]
        },
        "user_data": {
            "years_until_retirement": 25, 
            "target_retirement_income": 75000
        },
    }

    try:
        # Import and test
        from agent import process_portfolio_report
        
        print("🚀 Running full reporter agent test...")
        print(f"Portfolio value: ${payload['portfolio_data']['accounts'][0]['cash_balance'] + (50*450) + (100*85):,}")
        
        result = await process_portfolio_report(
            payload["job_id"], 
            payload["portfolio_data"], 
            payload["user_data"]
        )
        
        print("\n" + "="*50)
        print("RESULT:")
        print("="*50)
        print(json.dumps(result, indent=2))
        
        if result.get("success"):
            print("\n" + "="*50)
            print("GENERATED REPORT:")
            print("="*50)
            print(result.get("final_output", "No output"))
            print("✅ Full test completed successfully!")
        else:
            print("❌ Test failed:", result.get("error"))
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up - delete the test job and user
        try:
            db.jobs.delete(test_job_id)
            print(f"\n🧹 Deleted test job: {test_job_id}")
        except Exception as e:
            print(f"⚠️  Failed to delete test job: {e}")
        
        try:
            # Delete user using clerk_user_id
            db.client.delete("users", "clerk_user_id = :clerk_id", {"clerk_id": test_user_id})
            print(f"🧹 Deleted test user: {test_user_id}")
        except Exception as e:
            print(f"⚠️  Failed to delete test user: {e}")

if __name__ == "__main__":
    asyncio.run(test_full())