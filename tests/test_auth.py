"""
tests/test_auth.py
==================
Unit tests for password hashing with bcrypt, JWT token operations,
and auth schemas in the Sovereign AI Workbench.
"""

from datetime import timedelta
import pytest

from backend.security.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from backend.schemas.auth import UserLogin, UserRegister


def test_password_hashing():
    """Verify that bcrypt hashes passwords securely with salt and verifies matches."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    # Hash should not equal plaintext
    assert hashed != password
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    # Correct password verifies
    assert verify_password(password, hashed) is True

    # Incorrect password fails
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False


def test_jwt_token_encode_decode():
    """Verify JWT token claims encoding and decoding."""
    claims = {
        "sub": "user_12345",
        "email": "engineer@sovereign.local",
        "role": "engineer",
        "organization": "Sovereign Industrial",
    }

    token = create_access_token(claims, expires_delta=timedelta(minutes=30))
    assert isinstance(token, str)
    assert len(token) > 20

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user_12345"
    assert decoded["email"] == "engineer@sovereign.local"
    assert decoded["role"] == "engineer"
    assert "exp" in decoded


def test_jwt_expired_token():
    """Verify that expired JWT tokens return None."""
    claims = {"sub": "user_expired"}
    token = create_access_token(claims, expires_delta=timedelta(seconds=-10))
    decoded = decode_access_token(token)
    assert decoded is None


def test_auth_schemas():
    """Verify Pydantic user registration and login validation."""
    valid_reg = UserRegister(
        name="Alex Smith",
        email="alex@company.com",
        password="ValidPassword123",
        organization="Industrial Corp",
    )
    assert valid_reg.name == "Alex Smith"
    assert valid_reg.email == "alex@company.com"

    valid_login = UserLogin(
        email="alex@company.com",
        password="ValidPassword123",
    )
    assert valid_login.email == "alex@company.com"

