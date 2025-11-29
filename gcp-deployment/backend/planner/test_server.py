"""
Test script for Planner server
Creates a test job and processes it
"""

import requests
import uuid
import json

# Test server URL
BASE_URL = "http://localhost:8000"

def test_health_check():
    """Test health check endpoint"""
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_job_processing():
    """Test job processing with a valid UUID"""
    print("Testing job processing...")
    
    # Generate a valid UUID for testing
    test_job_id = str(uuid.uuid4())
    print(f"Using job ID: {test_job_id}")
    
    # First, we need to create a job in the database
    # For now, let's just test if the endpoint accepts the request
    # In a real scenario, the job would be created via the API first
    
    payload = {
        "job_id": test_job_id
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/",
            json=payload,
            timeout=30
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")

def test_with_existing_job():
    """Test with a job that exists in the database"""
    print("Testing with existing job...")
    print("Note: This requires a job to exist in the database.")
    print("Create a job via the API first, then use its ID here.")
    print()
    
    # You can get a real job ID from the database or API
    # For example, from a previous API call:
    # job_id = "your-actual-job-uuid-here"
    # payload = {"job_id": job_id}
    # response = requests.post(f"{BASE_URL}/", json=payload)

if __name__ == "__main__":
    print("=" * 50)
    print("Planner Server Test")
    print("=" * 50)
    print()
    
    # Test 1: Health check
    test_health_check()
    
    # Test 2: Job processing (will fail if job doesn't exist)
    print("Note: Job processing test requires a job to exist in the database.")
    print("The job_id must be a valid UUID and exist in the jobs table.")
    print()
    
    # Uncomment to test (will fail if job doesn't exist):
    # test_job_processing()

