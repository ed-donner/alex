"""
Test the Researcher Agent with comprehensive scenarios (full test).
"""

import os
from agent import create_agent_and_run

def test_specific_topics():
    """Test the researcher agent with various specific investment topics."""
    
    topics = [
        "Bitcoin ETF Analysis",
        "AI Semiconductor Stocks", 
        "Green Energy Investment Trends",
        "Real Estate Market Outlook",
        "Banking Sector Analysis"
    ]
    
    results = {}
    
    print("🔍 Testing Researcher Agent with Multiple Topics...")
    print(f"📊 Testing {len(topics)} different investment topics")
    
    for i, topic in enumerate(topics, 1):
        print(f"\n📈 Test {i}/{len(topics)}: {topic}")
        print("-" * 40)
        
        try:
            result = create_agent_and_run(topic)
            results[topic] = {
                "success": True,
                "result": result,
                "length": len(result) if result else 0
            }
            
            print(f"✅ Research completed for {topic}")
            print(f"📏 Response length: {len(result)} characters")
            
            # Show preview of result
            preview = result[:200] + "..." if len(result) > 200 else result
            print(f"📄 Preview: {preview}")
            
        except Exception as e:
            print(f"❌ Error researching {topic}: {e}")
            results[topic] = {
                "success": False,
                "error": str(e),
                "length": 0
            }
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 RESEARCHER AGENT TEST SUMMARY")
    print("=" * 60)
    
    successful_tests = [topic for topic, result in results.items() if result["success"]]
    failed_tests = [topic for topic, result in results.items() if not result["success"]]
    
    print(f"✅ Successful: {len(successful_tests)}/{len(topics)}")
    print(f"❌ Failed: {len(failed_tests)}/{len(topics)}")
    
    if successful_tests:
        print(f"\n🎯 Successful Topics:")
        for topic in successful_tests:
            length = results[topic]["length"]
            print(f"   - {topic}: {length} chars")
    
    if failed_tests:
        print(f"\n💥 Failed Topics:")
        for topic in failed_tests:
            error = results[topic]["error"]
            print(f"   - {topic}: {error}")
    
    # Analysis
    total_chars = sum(result["length"] for result in results.values() if result["success"])
    avg_length = total_chars / len(successful_tests) if successful_tests else 0
    
    print(f"\n📈 Analysis:")
    print(f"   Total characters generated: {total_chars:,}")
    print(f"   Average response length: {avg_length:.0f} chars")
    print(f"   Success rate: {len(successful_tests)/len(topics)*100:.1f}%")
    
    return results

def test_api_configuration():
    """Test different API configuration scenarios."""
    print("\n🔧 Testing API Configuration Scenarios...")
    
    # Save original values
    orig_endpoint = os.environ.get("ALEX_API_ENDPOINT")
    orig_key = os.environ.get("ALEX_API_KEY")
    
    scenarios = [
        {
            "name": "No API Configuration",
            "endpoint": None,
            "key": None,
            "expected": "Should note local mode"
        },
        {
            "name": "Partial Configuration",
            "endpoint": "https://example.com/api",
            "key": None,
            "expected": "Should handle missing key"
        },
        {
            "name": "Mock Full Configuration",
            "endpoint": "https://mock-api.alex.com/ingest",
            "key": "mock-api-key-123",
            "expected": "Should attempt ingestion (may fail)"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n🧪 Scenario {i}: {scenario['name']}")
        print(f"Expected: {scenario['expected']}")
        
        # Set environment
        if scenario["endpoint"]:
            os.environ["ALEX_API_ENDPOINT"] = scenario["endpoint"]
        elif "ALEX_API_ENDPOINT" in os.environ:
            del os.environ["ALEX_API_ENDPOINT"]
            
        if scenario["key"]:
            os.environ["ALEX_API_KEY"] = scenario["key"]
        elif "ALEX_API_KEY" in os.environ:
            del os.environ["ALEX_API_KEY"]
        
        try:
            result = create_agent_and_run("Quick API Test Topic")
            print(f"✅ Scenario completed")
            
            # Check if result mentions API issues
            result_lower = result.lower()
            if "api" in result_lower or "local" in result_lower or "config" in result_lower:
                print(f"📝 API-related content detected in response")
            
        except Exception as e:
            print(f"❌ Scenario failed: {e}")
    
    # Restore original values
    if orig_endpoint:
        os.environ["ALEX_API_ENDPOINT"] = orig_endpoint
    elif "ALEX_API_ENDPOINT" in os.environ:
        del os.environ["ALEX_API_ENDPOINT"]
        
    if orig_key:
        os.environ["ALEX_API_KEY"] = orig_key
    elif "ALEX_API_KEY" in os.environ:
        del os.environ["ALEX_API_KEY"]

def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n🔬 Testing Edge Cases...")
    
    edge_cases = [
        {
            "name": "Empty Topic",
            "topic": "",
            "description": "Test with empty string topic"
        },
        {
            "name": "Very Long Topic",
            "topic": "A" * 500,  # 500 character topic
            "description": "Test with extremely long topic"
        },
        {
            "name": "Special Characters",
            "topic": "Tesla Stock: P/E, ROI & Market Cap Analysis! @#$%",
            "description": "Test with special characters"
        },
        {
            "name": "Non-English Topic",
            "topic": "テスラ株式分析",  # Tesla stock analysis in Japanese
            "description": "Test with non-English characters"
        }
    ]
    
    for i, case in enumerate(edge_cases, 1):
        print(f"\n🧪 Edge Case {i}: {case['name']}")
        print(f"Description: {case['description']}")
        print(f"Topic: {case['topic'][:100]}{'...' if len(case['topic']) > 100 else ''}")
        
        try:
            result = create_agent_and_run(case["topic"])
            print(f"✅ Edge case handled successfully")
            print(f"📏 Response length: {len(result)} characters")
            
        except Exception as e:
            print(f"❌ Edge case failed: {e}")

def main():
    """Run all full tests."""
    print("🔍 RESEARCHER AGENT FULL TEST SUITE")
    print("=" * 60)
    
    # Set up environment
    os.environ.setdefault("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")
    os.environ.setdefault("BEDROCK_REGION", "us-west-2")
    
    try:
        # Run all test suites
        results = test_specific_topics()
        test_api_configuration()
        test_edge_cases()
        
        print("\n" + "=" * 60)
        print("🎯 FULL TEST SUITE COMPLETED")
        print("=" * 60)
        print("✅ All test categories executed")
        print("📊 Check individual results above for detailed analysis")
        
    except Exception as e:
        print(f"❌ Full test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()