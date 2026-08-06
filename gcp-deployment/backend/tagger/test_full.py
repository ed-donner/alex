#!/usr/bin/env python3
"""
Full test for Tagger agent via Lambda
"""

import os
import json
import boto3
from dotenv import load_dotenv

load_dotenv(override=True)

from src import Database

def test_tagger_lambda():
    """Test the Tagger agent via Lambda invocation"""
    
    db = Database()
    lambda_client = boto3.client('lambda')
    
    # Test instruments that need tagging
    test_instruments = [
        {"symbol": "ARKK", "name": "ARK Innovation ETF"},
        {"symbol": "SOFI", "name": "SoFi Technologies Inc"},
        {"symbol": "TSLA", "name": "Tesla Inc"}
    ]
    
    print("Testing Tagger Lambda")
    print("=" * 60)
    print(f"Instruments to tag: {[i['symbol'] for i in test_instruments]}")
    
    # Invoke Lambda
    try:
        response = lambda_client.invoke(
            FunctionName='alex-tagger',
            InvocationType='RequestResponse',
            Payload=json.dumps({'instruments': test_instruments})
        )
        
        result = json.loads(response['Payload'].read())
        print(f"\nLambda Response: {json.dumps(result, indent=2)}")
        
        # Check database for updated instruments
        print("\n✅ Checking database for tagged instruments:")
        for inst in test_instruments:
            instrument = db.instruments.find_by_symbol(inst['symbol'])
            if instrument:
                if instrument.get('allocation_asset_class'):
                    print(f"  ✅ {inst['symbol']}: Tagged successfully")
                    print(f"     Asset: {instrument.get('allocation_asset_class')}")
                    print(f"     Regions: {instrument.get('allocation_regions')}")
                else:
                    print(f"  ❌ {inst['symbol']}: No allocations found")
            else:
                print(f"  ⚠️  {inst['symbol']}: Not found in database")
                
    except Exception as e:
        print(f"Error invoking Lambda: {e}")
    
    print("=" * 60)

if __name__ == "__main__":
    test_tagger_lambda()