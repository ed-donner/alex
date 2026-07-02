#!/usr/bin/env python3
"""
Simple test for Tagger agent
"""

import asyncio
import json
from dotenv import load_dotenv

load_dotenv(override=True)

from agent import tagger_agent

def test_agent():
    """Test the Bedrock ESG Agent locally"""
    
    test_payload =  {
        "instruments": [
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF"},
            {"symbol": "ARKK", "name": "ARK Innovation ETF"},
            {"symbol": "SOFI", "name": "SoFi Technologies Inc"},
            {"symbol": "TSLA", "name": "Tesla Inc"}
        ]
    }
    
    print("Testing Bedrock Agent...")
    print("=" * 60)
    
    # Directly invoke the entrypoint function
    result = tagger_agent(test_payload)
    print(f"Status Code: {result['statusCode']}")
    
    if result['statusCode'] == 200:
        body = json.loads(result['body'])
        print(f"Tagged: {body.get('tagged', 0)} instruments")
        print(f"Updated: {body.get('updated', [])}")
        if body.get('classifications'):
            for c in body['classifications']:
                print(f"  {c['symbol']}: {c['type']}")
    else:
        print(f"Error: {result['body']}")
    
    print("=" * 60)

if __name__ == "__main__":
    test_agent()