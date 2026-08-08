"""
Test Data router handling test account population (static / live Polygon) and resetting.
"""

import time
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends, Query
from src.schemas import InstrumentCreate

import deps
from deps import get_current_user_id, logger

router = APIRouter(prefix="/api", tags=["Test Data"])


@router.delete("/reset-accounts")
async def reset_accounts(clerk_user_id: str = Depends(get_current_user_id)):
    """Delete all accounts for the current user"""
    try:
        user = deps.db.users.find_by_clerk_id(clerk_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        accounts = deps.db.accounts.find_by_user(clerk_user_id)

        deleted_count = 0
        for account in accounts:
            try:
                deps.db.accounts.delete(account["id"])
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Could not delete account {account['id']}: {e}")

        return {
            "message": f"Deleted {deleted_count} account(s)",
            "accounts_deleted": deleted_count,
        }

    except Exception as e:
        logger.error(f"Error resetting accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/populate-test-data")
async def populate_test_data(
    fetch_live_prices: bool = Query(False, description="Whether to query live Polygon market prices"),
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Populate test data for the current user, optionally fetching live market prices from Polygon"""
    try:
        user = deps.db.users.find_by_clerk_id(clerk_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        live_prices = {}
        if fetch_live_prices:
            try:
                from planner.prices import get_all_share_prices_polygon_eod
                logger.info("Fetching live Polygon market data for test data population...")
                live_prices = get_all_share_prices_polygon_eod()
                logger.info(f"Successfully retrieved live prices for {len(live_prices)} tickers from Polygon")
            except Exception as e:
                logger.warning(f"Could not fetch live Polygon prices: {e}")

        missing_instruments = {
            "AAPL": {"name": "Apple Inc.", "type": "stock", "current_price": 195.89, "allocation_regions": {"north_america": 100}, "allocation_sectors": {"technology": 100}, "allocation_asset_class": {"equity": 100}},
            "AMZN": {"name": "Amazon.com Inc.", "type": "stock", "current_price": 178.35, "allocation_regions": {"north_america": 100}, "allocation_sectors": {"consumer_discretionary": 100}, "allocation_asset_class": {"equity": 100}},
            "NVDA": {"name": "NVIDIA Corporation", "type": "stock", "current_price": 522.74, "allocation_regions": {"north_america": 100}, "allocation_sectors": {"technology": 100}, "allocation_asset_class": {"equity": 100}},
            "MSFT": {"name": "Microsoft Corporation", "type": "stock", "current_price": 430.82, "allocation_regions": {"north_america": 100}, "allocation_sectors": {"technology": 100}, "allocation_asset_class": {"equity": 100}},
            "GOOGL": {"name": "Alphabet Inc. Class A", "type": "stock", "current_price": 173.69, "allocation_regions": {"north_america": 100}, "allocation_sectors": {"technology": 100}, "allocation_asset_class": {"equity": 100}},
        }

        for symbol, info in missing_instruments.items():
            price_val = Decimal(str(live_prices.get(symbol, info["current_price"])))
            existing = deps.db.instruments.find_by_symbol(symbol)
            if not existing:
                try:
                    instrument_data = InstrumentCreate(
                        symbol=symbol,
                        name=info["name"],
                        instrument_type=info["type"],
                        current_price=price_val,
                        allocation_regions=info["allocation_regions"],
                        allocation_sectors=info["allocation_sectors"],
                        allocation_asset_class=info["allocation_asset_class"],
                    )
                    deps.db.instruments.create_instrument(instrument_data)
                    logger.info(f"Added missing instrument: {symbol} with price ${price_val}")
                except Exception as e:
                    logger.warning(f"Could not add instrument {symbol}: {e}")

        if fetch_live_prices and live_prices:
            cache_records = [
                {
                    "symbol": sym,
                    "price": float(prc),
                    "volume": 0,
                    "expires_at_epoch": int(time.time()) + 86400,
                    "source": "polygon_populate",
                }
                for sym, prc in live_prices.items()
            ]
            deps.db.market_cache.set_prices(cache_records)

        accounts_data = [
            {
                "name": "401k Long-term",
                "purpose": "Primary retirement savings account with employer match",
                "cash": 5000.00,
                "positions": [
                    ("SPY", 150),
                    ("VTI", 100),
                    ("BND", 200),
                    ("QQQ", 75),
                    ("IWM", 50),
                ],
            },
            {
                "name": "Roth IRA",
                "purpose": "Tax-free retirement growth account",
                "cash": 2500.00,
                "positions": [
                    ("VTI", 80),
                    ("VXUS", 60),
                    ("VNQ", 40),
                    ("GLD", 25),
                    ("TLT", 30),
                    ("VIG", 45),
                ],
            },
            {
                "name": "Brokerage Account",
                "purpose": "Taxable investment account for individual stocks",
                "cash": 10000.00,
                "positions": [
                    ("TSLA", 15),
                    ("AAPL", 50),
                    ("AMZN", 10),
                    ("NVDA", 25),
                    ("MSFT", 30),
                    ("GOOGL", 20),
                ],
            },
        ]

        created_accounts = []
        for account_data in accounts_data:
            account_id = deps.db.accounts.create_account(
                clerk_user_id=clerk_user_id,
                account_name=account_data["name"],
                account_purpose=account_data["purpose"],
                cash_balance=Decimal(str(account_data["cash"])),
            )

            for symbol, quantity in account_data["positions"]:
                try:
                    deps.db.positions.add_position(
                        account_id=account_id,
                        symbol=symbol,
                        quantity=Decimal(str(quantity)),
                    )
                except Exception as e:
                    logger.warning(f"Could not add position {symbol}: {e}")

            created_accounts.append(account_id)

        all_accounts = []
        for account_id in created_accounts:
            account = deps.db.accounts.find_by_id(account_id)
            positions = deps.db.positions.find_by_account(account_id)
            account["positions"] = positions
            all_accounts.append(account)

        return {
            "message": "Test data populated successfully",
            "accounts_created": len(created_accounts),
            "accounts": all_accounts,
        }

    except Exception as e:
        logger.error(f"Error populating test data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
