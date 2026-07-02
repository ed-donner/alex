"""
Test the Charter Agent with database integration (simple test).
"""

import os
import json
import uuid
import asyncio
from typing import Dict, Any

# Import database
from src import Database

# We'll import the agent entry point within the test function

def create_test_portfolio_data() -> Dict[str, Any]:
    """Create test portfolio data for charter agent."""
    return {
        "user_id": "test_user_charter",
        "job_id": None,  # Will be set after database job creation
        "accounts": [
            {
                "id": "charter_acc1",
                "name": "401(k)",
                "type": "401k",
                "cash_balance": 5000.0,
                "positions": [
                    {
                        "symbol": "SPY",
                        "quantity": 100.0,
                        "instrument": {
                            "symbol": "SPY",
                            "name": "SPDR S&P 500 ETF",
                            "current_price": 450.0,
                            "allocation_asset_class": {"equity": 100},
                            "allocation_regions": {"north_america": 100},
                            "allocation_sectors": {
                                "technology": 30,
                                "healthcare": 15,
                                "financials": 15,
                                "consumer_discretionary": 20,
                                "industrials": 20
                            }
                        }
                    },
                    {
                        "symbol": "BND",
                        "quantity": 50.0,
                        "instrument": {
                            "symbol": "BND",
                            "name": "Vanguard Total Bond Market ETF",
                            "current_price": 75.0,
                            "allocation_asset_class": {"fixed_income": 100},
                            "allocation_regions": {"north_america": 100},
                            "allocation_sectors": {"government": 70, "corporate": 30}
                        }
                    }
                ]
            },
            {
                "id": "charter_acc2",
                "name": "Roth IRA",
                "type": "roth_ira",
                "cash_balance": 2500.0,
                "positions": [
                    {
                        "symbol": "VTI",
                        "quantity": 75.0,
                        "instrument": {
                            "symbol": "VTI",
                            "name": "Vanguard Total Stock Market ETF",
                            "current_price": 220.0,
                            "allocation_asset_class": {"equity": 100},
                            "allocation_regions": {"north_america": 100},
                            "allocation_sectors": {
                                "technology": 25,
                                "healthcare": 14,
                                "financials": 13,
                                "consumer_discretionary": 12,
                                "industrials": 9,
                                "consumer_staples": 6,
                                "energy": 4,
                                "real_estate": 4,
                                "utilities": 3,
                                "materials": 3,
                                "telecommunications": 7
                            }
                        }
                    }
                ]
            }
        ]
    }

def test_charter_agent():
    """Test the charter agent with portfolio data."""
    print("🎨 Testing Charter Agent...")
    
    # Create test data
    portfolio_data = create_test_portfolio_data()
    job_id = portfolio_data["job_id"]  # Will be None initially
    user_id = portfolio_data["user_id"]
    
    print(f"📊 Job ID: {job_id if job_id else 'To be generated'}")
    print(f"👤 User ID: {user_id}")
    
    # Calculate total portfolio value for context
    total_value = 0.0
    for account in portfolio_data["accounts"]:
        total_value += float(account.get("cash_balance", 0))
        for position in account["positions"]:
            quantity = float(position["quantity"])
            price = float(position["instrument"]["current_price"])
            total_value += quantity * price
    
    print(f"💰 Total Portfolio Value: ${total_value:,.2f}")
    
    try:
        # Initialize database
        db = Database()
        print("📊 Database connected")
        
        # Create or find user
        try:
            user = db.users.find_by_clerk_id(user_id)
            if not user:
                # Use the correct method for creating users
                user_id_created = db.users.create_user(
                    clerk_user_id=user_id,
                    display_name='Charter Test',
                    years_until_retirement=25
                )
                print(f"👤 Created test user: {user_id_created}")
            else:
                print(f"👤 Found existing user: {user_id}")
        except Exception as e:
            print(f"⚠️ User setup warning: {e}")
        
        # Create job entry
        try:
            # Use the correct method for creating jobs
            created_job_id = db.jobs.create_job(
                clerk_user_id=user_id,
                job_type='portfolio_analysis',
                request_payload={'test': 'charter agent charts generation'}
            )
            print(f"💼 Created job with auto-generated ID: {created_job_id}")
            # Update our job_id to use the database-generated one
            job_id = created_job_id
            portfolio_data["job_id"] = str(created_job_id)  # Update string version too
        except Exception as e:
            print(f"⚠️ Job creation warning: {e}")
        
        # Run the charter agent (full agent with database saving)
        print("\n🎨 Running Charter Agent with database integration...")
        
        # Prepare event for the agent
        event = {
            'job_id': job_id,
            'portfolio_data': portfolio_data,
            'user_id': user_id
        }
        
        # Import the agent entry point
        from agent import chart_maker_agent
        
        # Run the agent asynchronously
        import asyncio
        result = asyncio.run(chart_maker_agent(event))
        
        print("📊 Charter Agent Result:")
        print("=" * 50)
        
        # Debug: Show raw result first
        print(f"🔍 Raw result type: {type(result)}")
        print(f"🔍 Raw result (first 500 chars): {str(result)[:500]}")
        
        # Try to parse and format the JSON result
        try:
            parsed_result = json.loads(result)
            print(f"🔍 Parsed result keys: {list(parsed_result.keys()) if isinstance(parsed_result, dict) else 'Not a dict'}")
            
            if "error" in parsed_result:
                print(f"❌ Error: {parsed_result['error']}")
            elif "success" in parsed_result and parsed_result.get("success"):
                # Handle the success response from chart_maker_agent
                print(f"✅ {parsed_result.get('message', 'Charts generated successfully')}")
                print(f"📊 Charts generated: {parsed_result.get('charts_generated', 'unknown')}")
                chart_keys = parsed_result.get('chart_keys', [])
                if chart_keys:
                    print(f"🔑 Chart keys: {chart_keys}")
                    
                # Since charts were processed and saved, skip detailed chart display
                # The database verification below will show the actual saved data
                
            elif "charts" in parsed_result:
                # Handle the response from create_agent_and_run (if called directly)
                charts = parsed_result["charts"]
                print(f"✅ Generated {len(charts)} charts:")
                
                for i, chart in enumerate(charts, 1):
                    print(f"\n📈 Chart {i}: {chart.get('title', 'Untitled')}")
                    print(f"   Type: {chart.get('type', 'unknown')}")
                    print(f"   Key: {chart.get('key', 'unknown')}")
                    print(f"   Description: {chart.get('description', 'No description')}")
                    
                    data_points = chart.get('data', [])
                    print(f"   Data Points: {len(data_points)}")
                    
                    # Show first few data points
                    for j, point in enumerate(data_points[:3]):
                        name = point.get('name', 'Unknown')
                        value = point.get('value', 0)
                        color = point.get('color', 'No color')
                        print(f"     {j+1}. {name}: ${value:,.2f} ({color})")
                    
                    if len(data_points) > 3:
                        print(f"     ... and {len(data_points) - 3} more")
                
                print(f"\n✅ Charter Agent successfully generated {len(charts)} charts")
            else:
                print("❓ Unexpected result format")
                print(f"� Available keys: {list(parsed_result.keys()) if isinstance(parsed_result, dict) else 'Not a dict'}")
                print(f"� Full result: {parsed_result}")
                print(result)
                
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON result: {e}")
            print("Raw result:")
            print(result)
        
        # Verify charts were saved to database (regardless of response format)
        print("\n🔍 Verifying charts saved to database...")
        try:
            # Query the database to check if charts were saved
            updated_job = db.jobs.find_by_id(job_id)
            if updated_job and updated_job.get('charts_payload'):
                charts_payload = updated_job['charts_payload']
                print(f"✅ Charts found in database!")
                print(f"📊 Number of chart keys in database: {len(charts_payload)}")
                print(f"🔑 Chart keys: {list(charts_payload.keys())}")
                
                # Verify each chart has expected structure
                for key, chart_data in charts_payload.items():
                    chart_type = chart_data.get('type', 'unknown')
                    data_points = len(chart_data.get('data', [])) if isinstance(chart_data.get('data'), list) else 0
                    print(f"   📈 {key}: type={chart_type}, data_points={data_points}")
                
                print("✅ Database verification successful!")
            else:
                print("❌ No charts found in database - save operation may have failed")
                if updated_job:
                    print(f"📋 Job found but charts_payload is: {updated_job.get('charts_payload', 'missing')}")
                else:
                    print(f"📋 Job {job_id} not found in database")
        except Exception as db_check_error:
            print(f"❌ Error checking database: {db_check_error}")
        
        print("\n" + "=" * 50)
        print("✅ Charter Agent test completed")
        
    except Exception as e:
        print(f"❌ Error during Charter Agent test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_charter_agent()