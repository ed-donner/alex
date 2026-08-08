"""
Instruments router handling autocomplete instrument lookup.
"""

from fastapi import APIRouter, HTTPException, Depends

import deps
from deps import get_current_user_id, logger

router = APIRouter(prefix="/api/instruments", tags=["Instruments"])


@router.get("")
async def list_instruments(clerk_user_id: str = Depends(get_current_user_id)):
    """Get all available instruments for autocomplete"""
    try:
        instruments = deps.db.instruments.find_all()
        return [
            {
                "symbol": inst["symbol"],
                "name": inst["name"],
                "instrument_type": inst["instrument_type"],
                "current_price": float(inst["current_price"]) if inst.get("current_price") else None,
            }
            for inst in instruments
        ]
    except Exception as e:
        logger.error(f"Error fetching instruments: {e}")
        raise HTTPException(status_code=500, detail=str(e))
