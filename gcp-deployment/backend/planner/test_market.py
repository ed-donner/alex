"""
Test market data fetching
"""

from src import Database
from market import update_instrument_prices

def test_market():
    db = Database()

    # Find a user with positions
    user_id = 'user_30BmVRQvPMVcGt9kWAH4BOy5Cjy'

    # Create a test job
    job_id = db.jobs.create_job(
        clerk_user_id=user_id,
        job_type='test_market',
        request_payload={'test': True}
    )

    print(f"Testing market data fetch for job {job_id}")

    # Get initial prices
    accounts = db.accounts.find_by_user(user_id)
    symbols = set()
    for account in accounts:
        positions = db.positions.find_by_account(account['id'])
        for position in positions:
            symbols.add(position['symbol'])
            instrument = db.instruments.find_by_symbol(position['symbol'])
            if instrument:
                print(f"  {position['symbol']}: Current price = ${instrument.get('current_price')}")

    print(f"\nFetching prices for {len(symbols)} symbols...")

    # Update prices
    update_instrument_prices(job_id, db)

    print("\nAfter update:")
    # Check updated prices
    for symbol in symbols:
        instrument = db.instruments.find_by_symbol(symbol)
        if instrument:
            print(f"  {symbol}: Current price = ${instrument.get('current_price')}")

    # Clean up
    db.jobs.delete(job_id)
    print(f"\nDeleted test job {job_id}")

if __name__ == "__main__":
    test_market()