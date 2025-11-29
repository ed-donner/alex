"""
Market data functions using polygon.io for fetching real-time prices.
"""

import logging
from typing import Set
from prices import get_share_price

logger = logging.getLogger()


def update_instrument_prices(job_id: str, db) -> None:
    """
    Fetch current prices for all instruments in the user's portfolio using polygon.io.
    Updates the instruments table with current prices.

    Args:
        job_id: The job ID to identify the user's portfolio
        db: Database instance
    """
    try:
        logger.info(f"Market: Fetching current prices for job {job_id}")

        # Get the job to find the user
        job = db.jobs.find_by_id(job_id)
        if not job:
            logger.error(f"Market: Job {job_id} not found")
            return

        user_id = job['clerk_user_id']

        # Get all unique symbols from user's positions
        accounts = db.accounts.find_by_user(user_id)
        symbols = set()

        for account in accounts:
            positions = db.positions.find_by_account(account['id'])
            for position in positions:
                symbols.add(position['symbol'])

        if not symbols:
            logger.info("Market: No symbols to update prices for")
            return

        logger.info(f"Market: Fetching prices for {len(symbols)} symbols: {symbols}")

        # Update prices for each symbol
        update_prices_for_symbols(symbols, db)

        logger.info("Market: Price update complete")

    except Exception as e:
        logger.error(f"Market: Error updating instrument prices: {e}")
        # Non-critical error, continue with analysis


def update_prices_for_symbols(symbols: Set[str], db) -> None:
    """
    Fetch and update prices for a set of symbols using polygon.io.

    Args:
        symbols: Set of ticker symbols to update
        db: Database instance
    """
    if not symbols:
        logger.info("Market: No symbols to update")
        return

    symbols_list = list(symbols)
    price_map = {}

    # Fetch price for each symbol using polygon.io
    for symbol in symbols_list:
        try:
            price = get_share_price(symbol)
            if price > 0:
                price_map[symbol] = price
                logger.info(f"Market: Retrieved {symbol} price: ${price:.2f}")
            else:
                logger.warning(f"Market: No price available for {symbol}")
        except Exception as e:
            logger.warning(f"Market: Could not fetch price for {symbol}: {e}")

    logger.info(f"Market: Retrieved prices for {len(price_map)}/{len(symbols_list)} symbols")

    # Update database with fetched prices
    for symbol, price in price_map.items():
        try:
            instrument = db.instruments.find_by_symbol(symbol)
            if instrument:
                update_data = {'current_price': price}
                success = db.client.update(
                    'instruments',
                    update_data,
                    "symbol = :symbol",
                    {'symbol': symbol}
                )
                if success:
                    logger.info(f"Market: Updated {symbol} price to ${price:.2f}")
                else:
                    logger.warning(f"Market: Failed to update price for {symbol}")
            else:
                logger.warning(f"Market: Instrument {symbol} not found in database")
        except Exception as e:
            logger.error(f"Market: Error updating {symbol} in database: {e}")

    # Log symbols that didn't get prices
    missing = set(symbols_list) - set(price_map.keys())
    if missing:
        logger.warning(f"Market: No prices found for: {missing}")


def get_all_portfolio_symbols(db) -> Set[str]:
    """
    Get all unique symbols across all users' portfolios.
    Useful for pre-fetching prices in batch operations.

    Args:
        db: Database instance

    Returns:
        Set of unique ticker symbols
    """
    symbols = set()

    try:
        # Get all positions (this might need pagination for large datasets)
        all_positions = db.db.execute(
            "SELECT DISTINCT symbol FROM positions"
        )

        for position in all_positions:
            if position['symbol']:
                symbols.add(position['symbol'])

    except Exception as e:
        logger.error(f"Market: Error fetching all symbols: {e}")

    return symbols