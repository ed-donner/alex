#!/usr/bin/env python3
"""
Test the researcher service by generating investment research.
Cross-platform script for Mac/Windows/Linux.
"""

import subprocess
import sys
import json
import requests
import argparse


def get_service_url():
    """Get the App Runner service URL from AWS."""
    try:
        # Get service ARN first
        result = subprocess.run([
            "aws", "apprunner", "list-services",
            "--query", "ServiceSummaryList[?ServiceName=='alex-researcher'].ServiceArn",
            "--output", "json"
        ], capture_output=True, text=True, check=True)
        
        service_arns = json.loads(result.stdout)
        if not service_arns:
            print("❌ App Runner service 'alex-researcher' not found.")
            print("   Have you deployed it yet? Run: python deploy.py")
            sys.exit(1)
        
        service_arn = service_arns[0]
        
        # Get service URL
        result = subprocess.run([
            "aws", "apprunner", "describe-service",
            "--service-arn", service_arn,
            "--query", "Service.ServiceUrl",
            "--output", "text"
        ], capture_output=True, text=True, check=True)
        
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error getting service URL: {e}")
        print("   Make sure AWS CLI is configured and you have the right permissions.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing AWS response: {e}")
        sys.exit(1)


def test_research(topic=None):
    """Test the researcher service with a topic."""
    # If no topic, let the agent pick one
    display_topic = topic if topic else "Agent's choice (trending topic)"
    
    # Get service URL
    print("Getting App Runner service URL...")
    service_url = get_service_url()
    
    if not service_url:
        print("❌ Could not get service URL")
        sys.exit(1)
    
    print(f"✅ Found service at: https://{service_url}")
    
    # Test health endpoint first
    print("\nChecking service health...")
    try:
        health_url = f"https://{service_url}/health"
        response = requests.get(health_url, timeout=10)
        response.raise_for_status()
        print("✅ Service is healthy")
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check failed: {e}")
        print("   The service may still be starting. Try again in a minute.")
        sys.exit(1)
    
    # Call research endpoint
    print(f"\n🔬 Generating research for: {display_topic}")
    print("   This will take 20-30 seconds as the agent researches and analyzes...")
    
    try:
        research_url = f"https://{service_url}/research"
        # Only include topic in payload if it's provided
        payload = {"topic": topic} if topic else {}
        response = requests.post(
            research_url,
            json=payload,
            timeout=180  # Give it 3 minutes for research
        )
        response.raise_for_status()
        
        # Parse and display the result
        result = response.json()
        
        print("\n✅ Research generated successfully!")
        print("\n" + "="*60)
        print("RESEARCH RESULT:")
        print("="*60)
        print(result)
        print("="*60)
        
        print("\n✅ The research has been automatically stored in your knowledge base.")
        print("   To verify, run:")
        print("     cd ../ingest")
        print("     uv run test_search_s3vectors.py")
        
    except requests.exceptions.Timeout:
        print("❌ Request timed out. The service might be under heavy load.")
        print("   Try again in a moment.")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"❌ Error calling research endpoint: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Error details: {error_detail}")
            except (json.JSONDecodeError, AttributeError):
                print(f"   Response: {e.response.text}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Test the Alex Researcher service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Let agent pick a trending topic
  uv run test_research.py
  
  # Research specific topic
  uv run test_research.py "Tesla competitive advantages"
  
  # Research another topic
  uv run test_research.py "Microsoft cloud revenue growth"
        """
    )
    parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        help="Investment topic to research (optional - agent will pick trending topic if not provided)"
    )
    
    args = parser.parse_args()
    test_research(args.topic)


if __name__ == "__main__":
    main()