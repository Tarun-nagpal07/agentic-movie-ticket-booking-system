from pydantic import BaseModel, Field
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from src.api import services
from src.utils.logger import get_logger
from src.utils.errors import handle_errors, ToolError
from src.tools.booking_tools import _resolve_movie_name_to_id
from src.utils.id_cleaner import (
    resolve_theater_id,
    resolve_movie_id,
    get_movie_title_by_id,
    get_theater_name_by_id
)

logger = get_logger(__name__)

class OffersRequest(BaseModel):
    movie_id: str | None = Field(default=None, description="Optional specific movie ID (e.g. m1)")
    movie_name: str | None = Field(default=None, description="Optional fuzzy movie name (e.g. pushpa)")
    theater_id: str | None = Field(default=None, description="Optional specific theater ID (e.g. t1)")
    theater_name: str | None = Field(default=None, description="Optional fuzzy theater name (e.g. PVR)")

@tool("list_offers", args_schema=OffersRequest)
@handle_errors(error_class=ToolError)
def list_offers(
    movie_id: str | None = None,
    movie_name: str | None = None,
    theater_id: str | None = None,
    theater_name: str | None = None,
    config: RunnableConfig = None
) -> dict:
    """
    List out all active coupon-based offers. 
    Use this when the user asks for offers, discounts, or coupons.
    Can be filtered by selected movie or theater.
    """
    user_id = config.get("configurable", {}).get("user_id") if config else None
    
    # 1. Resolve movie_id using movie_name if needed
    if movie_name and not movie_id:
        resolved_mid = _resolve_movie_name_to_id(movie_name)
        if resolved_mid:
            movie_id = resolved_mid
            
    # 2. Resolve theater_id using theater_name if needed
    if theater_name and not theater_id:
        # Fuzzy match theater name
        theaters = services.get_theaters_by_city(config.get("configurable", {}).get("city", "ahmedabad") if config else "ahmedabad")
        for t in theaters:
            if theater_name.lower() in t["name"].lower():
                theater_id = t["theater_id"]
                break

    if theater_id:
        theater_id = resolve_theater_id(theater_id)
    if movie_id:
        movie_id = resolve_movie_id(movie_id)

    # Fetch theater brand if theater_id is resolved
    theater_name_resolved = None
    if theater_id:
        t_details = services.get_theater_by_id(theater_id)
        if t_details:
            theater_name_resolved = t_details["name"]

    # 3. Retrieve active coupons
    coupons = services.get_active_coupons()
    applicable_coupons = []

    for c in coupons:
        # Check if user has already used this coupon
        is_used = False
        if user_id:
            is_used = services.has_user_used_coupon(user_id, c["coupon_code"])
            
        # Check applicability
        # Movie constraint
        if c["movie_id"] and movie_id and c["movie_id"] != movie_id:
            continue
            
        # Theater constraint
        if c["theater_id"] and theater_id and c["theater_id"] != theater_id:
            continue
            
        # Theater brand constraint
        if c["theater_brand"] and theater_name_resolved:
            if c["theater_brand"].lower() not in theater_name_resolved.lower():
                continue
        elif c["theater_brand"] and theater_name and not theater_name_resolved:
            # If we only have input theater_name but couldn't resolve details yet, do a check on the text
            if c["theater_brand"].lower() not in theater_name.lower():
                continue

        # Translate movie_id / theater_id to human readable titles for details
        restricted_movie = get_movie_title_by_id(c["movie_id"]) if c["movie_id"] else None
        restricted_theater = get_theater_name_by_id(c["theater_id"]) if c["theater_id"] else None
        
        status_label = "Already Used" if is_used else "Available"
        
        applicable_coupons.append({
            "coupon_code": c["coupon_code"],
            "discount_type": c["discount_type"],
            "discount_value": c["discount_value"],
            "description": c["description"],
            "status": status_label,
            "restricted_movie": restricted_movie,
            "restricted_theater": restricted_theater,
            "restricted_brand": c["theater_brand"]
        })

    return {"status": "success", "offers": applicable_coupons}

list_offers.handle_tool_error = True
