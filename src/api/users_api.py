from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

from src.api import services
from src.api.auth import get_current_user
from src.api.rate_limiter import RateLimiter
from src.db.seed import get_user_uuid

router = APIRouter()

rate_limit_dep = Depends(RateLimiter(limit=30, window=60, scope="users_api"))

class PreferencesUpdateRequest(BaseModel):
    favorite_genres: Optional[List[str]] = None
    preferred_theaters: Optional[List[str]] = None
    preferred_seat_type: Optional[str] = None
    preferred_format: Optional[str] = None
    language_pref: Optional[str] = None

@router.get("/{user_id}", dependencies=[rate_limit_dep])
def get_user_profile(user_id: str, current_user: dict = Depends(get_current_user)):
    # Simple check: map legacy u1/u2/u3 or verify UUID matches
    target_uuid = get_user_uuid(user_id) if not user_id.startswith("00000") and len(user_id) < 10 else user_id
    
    if current_user["user_id"] != target_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this user profile."
        )
    # Exclude password_hash
    profile = {k: v for k, v in current_user.items() if k != "password_hash"}
    return {"status": "success", "user": profile}

@router.put("/{user_id}/preferences", dependencies=[rate_limit_dep])
def update_user_preferences(user_id: str, request: PreferencesUpdateRequest, current_user: dict = Depends(get_current_user)):
    target_uuid = get_user_uuid(user_id) if not user_id.startswith("00000") and len(user_id) < 10 else user_id
    
    if current_user["user_id"] != target_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update this user's preferences."
        )
        
    preferences = {k: v for k, v in request.dict().items() if v is not None}
    
    try:
        services.update_user_preferences(current_user["user_id"], preferences)
        # Fetch updated user
        updated_user = services.get_user_by_id(current_user["user_id"], include_bookings=False)
        profile = {k: v for k, v in updated_user.items() if k != "password_hash"}
        return {"status": "success", "message": "Preferences updated successfully.", "user": profile}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update preferences: {e}"
        )
