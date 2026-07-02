"""
Test the Researcher Agent with browser tools (simple test).
Tests saving to database, verification, and proper cleanup.
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Add the database path to import the database modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))

from src.client import DataAPIClient
from src.models import Database
from src.schemas import JobCreate
from agent import create_agent_and_run

def test_researcher_agent_with_database():
    """Test the researcher agent and save results to database."""
    print("🔍 Testing Researcher Agent with Database Integration...")
    
    # Initialize database
    try:
        db = DataAPIClient()
        db_models = Database()
        print(f"🎯 Using {db.db_backend.upper()} backend")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        return False
    
    # Create a test job
    test_job = None
    try:
        job_create = JobCreate(
            clerk_user_id="test_user_001",
            job_type="instrument_research",
            request_payload={"topic": "Tesla Stock Analysis", "test": True}
        )
        job_id = db_models.jobs.create(job_create.model_dump())
        print(f"✅ Created test job: {job_id}")
        test_job = job_id
    except Exception as e:
        print(f"❌ Failed to create test job: {e}")
        return False
    
    # Test with a specific topic
    topic = "Tesla Stock Analysis"
    print(f"📊 Research Topic: {topic}")
    
    try:
        # Set up environment variables for testing
        os.environ.setdefault("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
        os.environ.setdefault("BEDROCK_REGION", "us-west-2")
        
        print(f"🌐 Using model: {os.environ.get('BEDROCK_MODEL_ID')}")
        print(f"🌍 Using region: {os.environ.get('BEDROCK_REGION')}")
        
        print("\n🔍 Running Researcher Agent...")
        
        # Add timeout to prevent hanging
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Researcher agent execution timed out")
        
        # Set a 5-minute timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(300)  # 5 minutes
        
        try:
            result = create_agent_and_run(topic)
        finally:
            signal.alarm(0)  # Cancel the alarm
        
        if not result:
            print("❌ No result from researcher agent")
            return False
            
        print(f"📊 Research completed, result length: {len(result)} characters")
        
        # Save result to database in report_payload
        try:
            report_payload = {
                "content": result,
                "topic": topic,
                "agent": "researcher",
                "generated_at": datetime.now().isoformat()
            }
            
            # Update the job with the research report
            db_models.jobs.update_report(test_job, report_payload)
            print("✅ Saved research report to database")
            
        except Exception as e:
            print(f"❌ Failed to save report to database: {e}")
            return False
        
        # Verify the record was saved correctly
        try:
            saved_job = db_models.jobs.find_by_id(test_job)
            if saved_job and saved_job.get('report_payload'):
                payload = saved_job['report_payload']
                print("✅ Verified report saved in database")
                print(f"   Report content length: {len(payload.get('content', ''))}")
                print(f"   Topic: {payload.get('topic')}")
                print(f"   Agent: {payload.get('agent')}")
                print(f"   Generated at: {payload.get('generated_at')}")
                
                # Show snippet of content
                content = payload.get('content', '')
                if content:
                    snippet = content[:200] + "..." if len(content) > 200 else content
                    print(f"   Content snippet: {snippet}")
                    
            else:
                print("❌ Report not found in database")
                return False
                
        except Exception as e:
            print(f"❌ Failed to verify database record: {e}")
            return False
        
        # Basic validation of the research content
        if result and len(result) > 50:
            print("✅ Researcher Agent generated substantial output")
        else:
            print("⚠️ Researcher Agent output seems short")
        
        if "Tesla" in result or "TSLA" in result:
            print("✅ Response appears to be about the requested topic")
        else:
            print("⚠️ Response may not be about the requested topic")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during Researcher Agent test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up - delete the test job
        if test_job:
            try:
                db_models.jobs.delete(test_job)
                print(f"✅ Deleted test job: {test_job}")
            except Exception as e:
                print(f"⚠️ Failed to delete test job {test_job}: {e}")

def test_researcher_agent():
    """Test the researcher agent with a specific topic."""
    print("🔍 Testing Researcher Agent with Browser...")
    
    # Test with a specific topic
    topic = "Tesla Stock Analysis"
    print(f"📊 Research Topic: {topic}")
    
    try:
        # Set up environment variables for testing
        os.environ.setdefault("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
        os.environ.setdefault("BEDROCK_REGION", "us-west-2")
        
        # Note: ALEX_API_ENDPOINT and ALEX_API_KEY should be set for document ingestion
        # If not set, the agent will note this in local mode
        
        print(f"🌐 Using model: {os.environ.get('BEDROCK_MODEL_ID')}")
        print(f"🌍 Using region: {os.environ.get('BEDROCK_REGION')}")
        
        print("\n🔍 Running Researcher Agent with Browser...")
        print("   The agent will use real browser automation to visit financial websites")
        result = create_agent_and_run(topic)
        
        print("📊 Researcher Agent Result:")
        print("=" * 50)
        print(result)
        print("=" * 50)
        
        # Basic validation
        if result and len(result) > 50:
            print("✅ Researcher Agent generated substantial output")
        else:
            print("⚠️ Researcher Agent output seems short or empty")
        
        if "Tesla" in result or "TSLA" in result:
            print("✅ Response appears to be about the requested topic")
        else:
            print("⚠️ Response may not be about the requested topic")
        
        # Check for browser activity indicators
        result_lower = result.lower()
        browser_indicators = ["website", "browser", "visited", "navigated", "page", "url"]
        if any(indicator in result_lower for indicator in browser_indicators):
            print("✅ Response indicates browser activity")
        else:
            print("⚠️ No clear evidence of browser usage in response")
        
        print("✅ Researcher Agent test completed")
        
    except Exception as e:
        print(f"❌ Error during Researcher Agent test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Starting Researcher Agent Tests")
    print("=" * 60)
    
    # Run the database integration test
    success = test_researcher_agent_with_database()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All tests completed successfully!")
        sys.exit(0)
    else:
        print("❌ Test failed!")
        sys.exit(1)