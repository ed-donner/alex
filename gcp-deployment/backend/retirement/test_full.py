#!/usr/bin/env python3
"""
Full test for Retirement agent via Lambda
"""

import os
import json
import boto3
import time
from dotenv import load_dotenv

load_dotenv(override=True)

from src import Database
from src.schemas import JobCreate

def test_retirement_lambda():
    """Test the Retirement agent via Lambda invocation"""
    
    db = Database()
    lambda_client = boto3.client('lambda')
    
    # Create test job
    test_user_id = "test_user_001"
    
    job_create = JobCreate(
        clerk_user_id=test_user_id,
        job_type="portfolio_analysis",
        request_payload={"analysis_type": "test", "test": True}
    )
    job_id = db.jobs.create(job_create.model_dump())
    
    print(f"Testing Retirement Lambda with job {job_id}")
    print("=" * 60)
    
    # Invoke Lambda
    try:
        response = lambda_client.invoke(
            FunctionName='alex-retirement',
            InvocationType='RequestResponse',
            Payload=json.dumps({'job_id': job_id})
        )
        
        result = json.loads(response['Payload'].read())
        print(f"Lambda Response: {json.dumps(result, indent=2)}")
        
        # Check database for results
        time.sleep(2)  # Give it a moment
        job = db.jobs.find_by_id(job_id)
        
        if job and job.get('retirement_payload'):
            print("\n✅ Retirement analysis generated successfully!")
            print(f"Analysis preview: {json.dumps(job['retirement_payload'], indent=2)[:500]}...")
        else:
            print("\n❌ No retirement analysis found in database")
            
    except Exception as e:
        print(f"Error invoking Lambda: {e}")
    
    print("=" * 60)

if __name__ == "__main__":
    test_retirement_lambda()