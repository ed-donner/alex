"""
User router handling user profile creation, retrieval, and settings updates.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from fastapi_clerk_auth import HTTPAuthorizationCredentials

import deps
from deps import get_current_user_id, clerk_guard, logger

router = APIRouter(prefix="/api/user", tags=["User"])


class UserResponse(BaseModel):
    user: Dict[str, Any]
    created: bool


class UserUpdate(BaseModel):
    """Update user settings"""
    display_name: Optional[str] = None
    years_until_retirement: Optional[int] = None
    target_retirement_income: Optional[float] = None
    asset_class_targets: Optional[Dict[str, float]] = None
    region_targets: Optional[Dict[str, float]] = None


@router.get("", response_model=UserResponse)
async def get_or_create_user(
    clerk_user_id: str = Depends(get_current_user_id),
    creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
):
    """Get user or create if first time"""
    try:
        user = deps.db.users.find_by_clerk_id(clerk_user_id)
        if user:
            return UserResponse(user=user, created=False)

        token_data = creds.decoded
        display_name = (
            token_data.get("name")
            or token_data.get("email", "").split("@")[0]
            or "New User"
        )

        user_data = {
            "clerk_user_id": clerk_user_id,
            "display_name": display_name,
            "years_until_retirement": 20,
            "target_retirement_income": 60000,
            "asset_class_targets": {"equity": 70, "fixed_income": 30},
            "region_targets": {"north_america": 50, "international": 50},
        }

        deps.db.users.db.insert("users", user_data, returning="clerk_user_id")
        created_user = deps.db.users.find_by_clerk_id(clerk_user_id)
        logger.info(f"Created new user: {clerk_user_id}")
        return UserResponse(user=created_user, created=True)

    except Exception as e:
        logger.error(f"Error in get_or_create_user: {e}")
        raise HTTPException(status_code=500, detail="Failed to load user profile")


@router.put("")
async def update_user(
    user_update: UserUpdate,
    clerk_user_id: str = Depends(get_current_user_id),
):
    """Update user settings"""
    try:
        user = deps.db.users.find_by_clerk_id(clerk_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        update_data = user_update.model_dump(exclude_unset=True)
        deps.db.users.db.update(
            "users",
            update_data,
            "clerk_user_id = :clerk_user_id",
            {"clerk_user_id": clerk_user_id},
        )

        updated_user = deps.db.users.find_by_clerk_id(clerk_user_id)
        return updated_user

    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))
