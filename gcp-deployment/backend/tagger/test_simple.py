#!/usr/bin/env python3
"""
Simple test for Tagger agent
"""

import asyncio
import json
from dotenv import load_dotenv

load_dotenv(override=True)

from lambda_handler import lambda_handler

def test_tagger():
    """Test the tagger agent with unknown instruments"""
    
    test_event = {
        "instruments": [
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF"}
        ]
    }
    
    print("Testing Tagger Agent...")
    print("=" * 60)
    
    result = lambda_handler(test_event, None)
    
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
    test_tagger()