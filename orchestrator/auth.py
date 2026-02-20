"""
Authentication module for the orchestrator API
"""
import os
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Configuration from environment
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
# Use a simple SHA256 hash for now due to bcrypt compatibility issues
# Default password: MindAdmin123
AUTH_PASSWORD_HASH = os.getenv("AUTH_PASSWORD_HASH", "sha256:7c4a8d09ca3762af61e59520943dc26494f8941b:23d42f5f3f66498b2c8ff4c20b8c5ac826e47146")
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret-key-in-production")
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "24"))
ALGORITHM = "HS256"

# Security scheme
security = HTTPBearer()

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    # Simple SHA256 verification due to bcrypt compatibility issues
    # Format: sha256:salt:hash
    if hashed_password.startswith("sha256:"):
        _, salt, expected_hash = hashed_password.split(":", 2)
        actual_hash = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
        return hmac.compare_digest(actual_hash, expected_hash)

    # Fallback for plain comparison (not recommended for production)
    return plain_password == hashed_password

def authenticate_user(username: str, password: str) -> bool:
    """Authenticate user with username and password"""
    if username != AUTH_USERNAME:
        return False
    return verify_password(password, AUTH_PASSWORD_HASH)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=SESSION_TIMEOUT)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token from Authorization header"""
    token = credentials.credentials

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return username
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Optional: Create a dependency for optional authentication (for public endpoints)
async def verify_token_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Verify JWT token if provided, otherwise return None"""
    if not credentials:
        return None

    try:
        return await verify_token(credentials)
    except HTTPException:
        return None

def hash_password(password: str) -> str:
    """Hash a password for storing in config"""
    # Generate a random salt and hash with PBKDF2-SHA256
    import secrets
    salt = secrets.token_hex(16)
    hash_value = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
    return f"sha256:{salt}:{hash_value}"

# Utility function to generate password hash
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        password = sys.argv[1]
        print(f"Password hash for '{password}':")
        print(hash_password(password))
        print("\nAdd this to your .env file as AUTH_PASSWORD_HASH")
    else:
        print("Usage: python auth.py <password>")
        print("This will generate a bcrypt hash for the password")