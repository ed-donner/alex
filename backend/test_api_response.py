#!/usr/bin/env python3
"""Test API response format for chart data"""

import os
import sys
import json
import requests
from pathlib import Path

from database.src import Database

def test_api_response():
    """Test how the API returns chart data"""
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # First, get a job with chart data from database
    db = Database()
    
    sql = """
        SELECT id, clerk_user_id, charts_payload
        FROM jobs
        WHERE charts_payload IS NOT NULL
        LIMIT 1
    """
    
    result = db.execute_raw(sql, {})
    
    if not result.get('records'):
        print("❌ No jobs with chart data found")
        return
    
    job_data = result['records'][0]
    job_id = job_data[0]['stringValue']
    user_id = job_data[1]['stringValue']
    charts_raw = job_data[2]
    
    print(f"✅ Found job {job_id} for user {user_id}")
    print(f"Charts data type: {type(charts_raw)}")
    
    if isinstance(charts_raw, str):
        print("❌ Charts data is still a string, not parsed")
        print(f"Sample: {charts_raw[:200]}...")
    elif isinstance(charts_raw, dict):
        print("✅ Charts data is properly parsed as dict")
        print(f"Chart keys: {list(charts_raw.keys())}")
    else:
        print(f"⚠️  Unexpected charts data type: {type(charts_raw)}")
    
    # Now test the API endpoint
    api_base_url = os.getenv('API_BASE_URL', 'http://localhost:3000')
    
    # Assuming we need to test locally, let's just check the database response format
    # for now since the API might require authentication
    
    print("\n📋 Database response format analysis:")
    print(f"Job ID field type: {type(job_data[0])}")
    print(f"User ID field type: {type(job_data[1])}")
    print(f"Charts field type: {type(job_data[2])}")
    
    # Test using the Jobs model directly
    job_from_model = db.jobs.find_by_id(job_id)
    print(f"\n📝 Jobs model response:")
    print(f"Type: {type(job_from_model)}")
    if job_from_model:
        charts_from_model = job_from_model.get('charts_payload')
        print(f"Charts payload type: {type(charts_from_model)}")
        if isinstance(charts_from_model, dict):
            print(f"✅ Model correctly parses JSON - keys: {list(charts_from_model.keys())}")
        else:
            print(f"❌ Model doesn't parse JSON - type: {type(charts_from_model)}")

if __name__ == "__main__":
    test_api_response()