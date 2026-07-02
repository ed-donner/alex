#!/usr/bin/env python3
"""
Check database for payload data after test
"""

import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Add database path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))

from src import Database

def check_latest_job():
    """Check the latest job in the database for payload data"""
    db = Database()
    
    # Get the most recent job
    jobs = db.jobs.find_by_user("test_user_001", limit=1)
    if not jobs:
        print("No jobs found for test_user_001")
        return
    
    job = jobs[0]
    job_id = job['id']
    
    print(f"Job ID: {job_id}")
    print(f"Status: {job.get('status', 'N/A')}")
    print(f"Created: {job.get('created_at', 'N/A')}")
    print()
    
    # Check for payloads
    print("Payload Status:")
    print(f"- report_payload: {'✅ Present' if job.get('report_payload') else '❌ Missing'}")
    print(f"- charts_payload: {'✅ Present' if job.get('charts_payload') else '❌ Missing'}")
    print(f"- retirement_payload: {'✅ Present' if job.get('retirement_payload') else '❌ Missing'}")
    print()
    
    # Show payload contents (truncated)
    for payload_type in ['report_payload', 'charts_payload', 'retirement_payload']:
        payload = job.get(payload_type)
        if payload:
            print(f"{payload_type}:")
            if isinstance(payload, dict):
                for key, value in payload.items():
                    if isinstance(value, str) and len(value) > 100:
                        print(f"  {key}: {value[:100]}...")
                    else:
                        print(f"  {key}: {value}")
            else:
                print(f"  {str(payload)[:200]}...")
            print()

if __name__ == "__main__":
    check_latest_job()