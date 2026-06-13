import random
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field

from src.config.settings import settings
from src.config.constants import Limits
from src.db.postgres import get_db_cursor
from src.utils.rate_limiter import RateLimiter
from src.api import services
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()
security_scheme = HTTPBearer()

# City Centroids
CITY_CENTROIDS = {
    "ahmedabad": (23.0225, 72.5714),
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.6139, 77.2090),
    "bangalore": (12.9716, 77.5946)
}

CITY_MAPPING = {
    "ahm": "ahmedabad",
    "ahmedabad": "ahmedabad",
    "mum": "mumbai",
    "mumbai": "mumbai",
    "bang": "bangalore",
    "bangalore": "bangalore",
    "delhi": "delhi"
}

# --- Pydantic Schemas ---

class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=50)
    city: str
    phone: str = Field(..., min_length=10, max_length=15)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    user_id: str
    name: str
    token: str
    expires_at: str

# --- JWT helpers ---

def create_jwt_token(user_id: str) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "exp": expires_at
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    return token, expires_at

def store_session(user_id: str, token: str, expires_at: datetime):
    with get_db_cursor() as cur:
        # Delete any existing sessions for this user to simplify single-token scheme
        cur.execute("DELETE FROM user_sessions WHERE user_id = %s;", (user_id,))
        cur.execute("""
            INSERT INTO user_sessions (user_id, token, expires_at)
            VALUES (%s, %s, %s);
        """, (user_id, token, expires_at))

def delete_session(token: str):
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM user_sessions WHERE token = %s;", (token,))

# --- Dependency ---

async def get_current_user(cred: HTTPAuthorizationCredentials = Depends(security_scheme)) -> dict:
    token = cred.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    except jwt.ExpiredSignatureError:
        delete_session(token)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")

    # Check database session record
    with get_db_cursor() as cur:
        cur.execute("SELECT expires_at FROM user_sessions WHERE token = %s;", (token,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid or logged out")
        
        expires_at = row[0]
        # Make timezone-aware comparison
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
            
        if expires_at < datetime.now(timezone.utc):
            delete_session(token)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user = services.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        
    return user

# --- Endpoints ---

@router.post("/signup", response_model=TokenResponse, dependencies=[Depends(RateLimiter(limit=5, window=60, scope="auth_signup"))])
def signup(request: SignupRequest):
    email = request.email.lower()
    
    # 1. Resolve City & generate random lat/long
    mapped_city = CITY_MAPPING.get(request.city.lower())
    if not mapped_city:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Invalid city. Must be one of: {list(CITY_CENTROIDS.keys())}"
        )
        
    lat_c, lon_c = CITY_CENTROIDS[mapped_city]
    # randomly generated coordinates near the city centroid (+/- 0.02 degrees)
    latitude = lat_c + random.uniform(-0.02, 0.02)
    longitude = lon_c + random.uniform(-0.02, 0.02)

    # 2. Check duplicate email
    existing_user = services.get_user_by_email(email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered"
        )

    # 3. Hash password
    pwd_hash = bcrypt.hashpw(request.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # 4. Create user
    try:
        user_info = services.create_user(
            name=request.name,
            email=email,
            password_hash=pwd_hash,
            phone=request.phone,
            city=mapped_city,
            latitude=latitude,
            longitude=longitude
        )
    except Exception as e:
        logger.error(f"Failed to create user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user"
        )

    # 5. Issue Token & Store Session
    token, expires_at = create_jwt_token(user_info["user_id"])
    store_session(user_info["user_id"], token, expires_at)

    return {
        "user_id": user_info["user_id"],
        "name": user_info["name"],
        "token": token,
        "expires_at": expires_at.isoformat()
    }

@router.post("/login", response_model=TokenResponse, dependencies=[Depends(RateLimiter(limit=10, window=60, scope="auth_login"))])
def login(request: LoginRequest):
    user = services.get_user_by_email(request.email.lower())
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check password
    if not bcrypt.checkpw(request.password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Issue Token & Store Session
    token, expires_at = create_jwt_token(user["user_id"])
    store_session(user["user_id"], token, expires_at)

    return {
        "user_id": user["user_id"],
        "name": user["name"],
        "token": token,
        "expires_at": expires_at.isoformat()
    }

@router.post("/logout")
def logout(cred: HTTPAuthorizationCredentials = Depends(security_scheme)):
    delete_session(cred.credentials)
    return {"status": "success", "message": "Logged out successfully"}

@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    # exclude password_hash when returning user details
    profile = {k: v for k, v in current_user.items() if k != "password_hash"}
    return {"status": "success", "user": profile}
