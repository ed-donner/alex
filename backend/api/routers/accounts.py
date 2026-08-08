"""
Accounts router handling account listing, creation, updates, deletion, and position listing per account.
"""

from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from src.schemas import AccountCreate

import deps
from deps import get_current_user_id, logger

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])


class AccountUpdate(BaseModel):
    """Update account"""
    account_name: Optional[str] = None
    account_purpose: Optional[str] = None
    cash_balance: Optional[float] = None


@router.get("")
async def list_accounts(clerk_user_id: str = Depends(get_current_user_id)):
    """List user's accounts"""
    try:
        accounts = deps.db.accounts.find_by_user(clerk_user_id)
        return accounts
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_account(
    account: AccountCreate,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Create new account"""
    try:
        user = deps.db.users.find_by_clerk_id(clerk_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        account_id = deps.db.accounts.create_account(
            clerk_user_id=clerk_user_id,
            account_name=account.account_name,
            account_purpose=account.account_purpose,
            cash_balance=getattr(account, "cash_balance", Decimal("0")),
        )

        created_account = deps.db.accounts.find_by_id(account_id)
        return created_account
    except Exception as e:
        logger.error(f"Error creating account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{account_id}")
async def update_account(
    account_id: str,
    account_update: AccountUpdate,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Update account"""
    try:
        account = deps.db.accounts.find_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if account.get("clerk_user_id") != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        update_data = account_update.model_dump(exclude_unset=True)
        deps.db.accounts.update(account_id, update_data)

        updated_account = deps.db.accounts.find_by_id(account_id)
        return updated_account

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{account_id}")
async def delete_account(
    account_id: str,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Delete an account and all its positions"""
    try:
        account = deps.db.accounts.find_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if account.get("clerk_user_id") != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        positions = deps.db.positions.find_by_account(account_id)
        for position in positions:
            deps.db.positions.delete(position["id"])

        deps.db.accounts.delete(account_id)
        return {"message": "Account deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{account_id}/positions")
async def list_positions(
    account_id: str,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Get positions for account"""
    try:
        account = deps.db.accounts.find_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if account.get("clerk_user_id") != clerk_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        positions = deps.db.positions.find_by_account(account_id)

        formatted_positions = []
        for pos in positions:
            instrument = deps.db.instruments.find_by_symbol(pos["symbol"])
            formatted_positions.append({**pos, "instrument": instrument})

        return {"positions": formatted_positions}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
