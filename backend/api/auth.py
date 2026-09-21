from datetime import datetime, timezone
import logging
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.core.database import get_database, is_mongo_connected
from backend.schemas.auth import (
    TokenResponse,
    TokenVerifyResponse,
    UserLogin,
    UserProfile,
    UserRegister,
)
from backend.security.auth import (
    create_access_token,
    decode_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class TokenVerifyRequest(BaseModel):
    token: str | None = None


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserRegister):
    """Register a new user account with hashed password and MongoDB persistence."""
    db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured. Please ensure MONGODB_URI is configured in .env.local.",
        )

    normalized_email = payload.email.lower().strip()

    # Check for existing user
    existing_user = await db.users.find_one({"email": normalized_email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # Hash password with bcrypt
    hashed = hash_password(payload.password)
    now = datetime.now(timezone.utc)

    user_doc = {
        "email": normalized_email,
        "password_hash": hashed,
        "name": payload.name.strip(),
        "organization": payload.organization.strip() if payload.organization else None,
        "role": "operator",
        "created_at": now,
        "last_login": now,
    }

    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    # Issue JWT token
    token_claims = {
        "sub": user_id,
        "user_id": user_id,
        "email": normalized_email,
        "name": user_doc["name"],
        "organization": user_doc["organization"],
        "role": user_doc["role"],
    }
    access_token = create_access_token(token_claims)

    user_profile = UserProfile(
        id=user_id,
        email=normalized_email,
        name=user_doc["name"],
        organization=user_doc["organization"],
        role=user_doc["role"],
        created_at=now,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_profile,
    )


@router.post("/login", response_model=TokenResponse)
async def login_user(payload: UserLogin):
    """Authenticate with work email and password; returns JWT token on success."""
    db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured. Please ensure MONGODB_URI is configured in .env.local.",
        )

    normalized_email = payload.email.lower().strip()
    user_doc = await db.users.find_one({"email": normalized_email})

    if not user_doc or not verify_password(payload.password, user_doc.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login timestamp
    user_id = str(user_doc["_id"])
    now = datetime.now(timezone.utc)
    await db.users.update_one({"_id": user_doc["_id"]}, {"$set": {"last_login": now}})

    token_claims = {
        "sub": user_id,
        "user_id": user_id,
        "email": normalized_email,
        "name": user_doc.get("name", ""),
        "organization": user_doc.get("organization"),
        "role": user_doc.get("role", "operator"),
    }
    access_token = create_access_token(token_claims)

    user_profile = UserProfile(
        id=user_id,
        email=normalized_email,
        name=user_doc.get("name", ""),
        organization=user_doc.get("organization"),
        role=user_doc.get("role", "operator"),
        created_at=user_doc.get("created_at"),
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_profile,
    )


@router.post("/verify", response_model=TokenVerifyResponse)
async def verify_token_endpoint(
    payload: TokenVerifyRequest | None = None,
    current_user: UserProfile | None = Depends(lambda: None),
):
    """Verify an access token from Bearer header or JSON request body."""
    # Check if header provided
    try:
        user = await get_current_user()
        return TokenVerifyResponse(valid=True, user=user)
    except HTTPException:
        pass

    if payload and payload.token:
        decoded = decode_access_token(payload.token)
        if decoded:
            return TokenVerifyResponse(
                valid=True,
                user=UserProfile(
                    id=decoded.get("sub", ""),
                    email=decoded.get("email", ""),
                    name=decoded.get("name", ""),
                    organization=decoded.get("organization"),
                    role=decoded.get("role", "operator"),
                ),
            )

    return TokenVerifyResponse(valid=False, user=None)


@router.get("/me", response_model=UserProfile)
async def get_my_profile(current_user: UserProfile = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return current_user


@router.post("/logout")
async def logout_user():
    """Stateless logout confirmation."""
    return {"message": "Logged out successfully."}

