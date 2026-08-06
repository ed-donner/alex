from database.src import Database
import json

db = Database()

# Get the most recent completed job
jobs = db.jobs.find_all()
sorted_jobs = sorted(jobs, key=lambda x: x['created_at'], reverse=True)

# Find first completed job
completed_job = None
for job in sorted_jobs:
    if job['status'] == 'completed':
        completed_job = job
        break

if completed_job:
    print(f"Examining job: {completed_job['id']}")
    print(f"Status: {completed_job['status']}")
    print(f"Created: {completed_job['created_at']}")
    print(f"Updated: {completed_job.get('updated_at', 'N/A')}")

    # Check all fields
    for key, value in completed_job.items():
        if key == 'results':
            if value:
                print(f"\n{key}: Present")
                try:
                    results = json.loads(value) if isinstance(value, str) else value
                    print(f"  Keys in results: {list(results.keys())}")
                    for r_key in results:
                        if isinstance(results[r_key], str):
                            print(f"    {r_key}: {len(results[r_key])} chars")
                        elif isinstance(results[r_key], list):
                            print(f"    {r_key}: {len(results[r_key])} items")
                        elif isinstance(results[r_key], dict):
                            print(f"    {r_key}: dict with keys {list(results[r_key].keys())}")
                except Exception as e:
                    print(f"  Error parsing results: {e}")
                    print(f"  Raw value type: {type(value)}")
                    print(f"  Raw value (first 500 chars): {str(value)[:500]}")
            else:
                print(f"\n{key}: None/Empty")
        elif key not in ['id', 'status', 'created_at', 'updated_at']:
            if value:
                value_str = str(value)
                if len(value_str) > 100:
                    print(f"{key}: {value_str[:100]}...")
                else:
                    print(f"{key}: {value_str}")
else:
    print("No completed jobs found")