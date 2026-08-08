"""
Positions router handling position creation, updates, and deletion.
"""

from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from src.schemas import PositionCreate, InstrumentCreate

import deps
from deps import get_current_user_id, logger

router = APIRouter(prefix="/api/positions", tags=["Positions"])


class PositionUpdate(BaseModel):
    """Update position"""
    quantity: Optional[float] = None


@router.post("")
async def create_position(
    position: PositionCreate,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Create position"""
    try:
        account = deps.db.accounts.find_by_id(position.account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if account.get("clerk_user_id") != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        symbol_upper = position.symbol.upper()
        instrument = deps.db.instruments.find_by_symbol(symbol_upper)
        if not instrument:
            logger.info(f"Creating new instrument: {symbol_upper}")
            instrument_type = "stock" if len(symbol_upper) <= 5 and symbol_upper.isalpha() else "etf"

            new_instrument = InstrumentCreate(
                symbol=symbol_upper,
                name=f"{symbol_upper} - User Added",
                instrument_type=instrument_type,
                current_price=Decimal("0.00"),
                allocation_regions={"north_america": 100.0},
                allocation_sectors={"other": 100.0},
                allocation_asset_class={"equity": 100.0} if instrument_type == "stock" else {"fixed_income": 100.0},
            )
            deps.db.instruments.create_instrument(new_instrument)

        position_id = deps.db.positions.add_position(
            account_id=position.account_id,
            symbol=symbol_upper,
            quantity=position.quantity,
        )

        created_position = deps.db.positions.find_by_id(position_id)
        return created_position

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{position_id}")
async def update_position(
    position_id: str,
    position_update: PositionUpdate,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Update position"""
    try:
        position = deps.db.positions.find_by_id(position_id)
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")

        account = deps.db.accounts.find_by_id(position["account_id"])
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if account.get("clerk_user_id") != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        update_data = position_update.model_dump(exclude_unset=True)
        deps.db.positions.update(position_id, update_data)

        updated_position = deps.db.positions.find_by_id(position_id)
        return updated_position

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{position_id}")
async def delete_position(
    position_id: str,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Delete position"""
    try:
        position = deps.db.positions.find_by_id(position_id)
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")

        account = deps.db.accounts.find_by_id(position["account_id"])
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if account.get("clerk_user_id") != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        deps.db.positions.delete(position_id)
        return {"message": "Position deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting position: {e}")
        raise HTTPException(status_code=500, detail=str(e))
