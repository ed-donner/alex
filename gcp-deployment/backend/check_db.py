from database.src import Database

db = Database()
print("Checking instrument prices...")
instruments = db.instruments.find_all()
print(f"Found {len(instruments)} instruments")
for inst in instruments:
    price = inst.get("current_price")
    symbol = inst.get("symbol")
    if price:
        price_val = float(price) if isinstance(price, str) else price
        print(f"  {symbol}: ${price_val:.2f}")
    else:
        print(f"  {symbol}: N/A")

print("\nChecking recent jobs...")
jobs = db.jobs.find_all()
print(f"Found {len(jobs)} total jobs")

# Sort jobs by created_at and show last 5
sorted_jobs = sorted(jobs, key=lambda x: x['created_at'], reverse=True)[:5]
for job in sorted_jobs:
    print(f"  Job {job['id'][:8]}...: {job['status']} - {job['created_at']}")
    if job.get('results'):
        print(f"    Has results: Yes (length: {len(str(job['results']))} chars)")
        # Check if it's JSON data
        import json
        try:
            results = json.loads(job['results']) if isinstance(job['results'], str) else job['results']
            if 'charter' in results:
                print(f"    Charter data: {len(results['charter'])} charts")
        except:
            pass
    else:
        print(f"    Has results: No")