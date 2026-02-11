"""
Authentication middleware and dependencies for P-Auth RC.

Supports two authentication modes:
1. JWT Bearer tokens (for user sessions)
2. API Key authentication (for service-to-service calls)

Both modes can be used interchangeably on protected endpoints.
"""

from typing import Optional
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from pydantic import BaseModel


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# API Keys should be stored securely (database, secrets manager)
# For MVP, we use environment variable with comma-separated keys
VALID_API_KEYS = set(
    key.strip()
    for key in os.getenv("API_KEYS", "").split(",")
    if key.strip()
)


# ---------------------------------------------------------
# Security schemes
# ---------------------------------------------------------
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ---------------------------------------------------------
# Models
# ---------------------------------------------------------
class TokenData(BaseModel):
    """Data extracted from JWT token."""
    username: Optional[str] = None
    user_id: Optional[str] = None
    scopes: list[str] = []


# ---------------------------------------------------------
# JWT Token Functions
# ---------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_jwt_token(token: str) -> TokenData:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenData with extracted claims

    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        scopes: list = payload.get("scopes", [])

        if username is None:
            raise credentials_exception

        return TokenData(username=username, user_id=user_id, scopes=scopes)
    except JWTError:
        raise credentials_exception


def verify_api_key(api_key: str) -> bool:
    """
    Verify an API key against the list of valid keys.

    Args:
        api_key: API key string

    Returns:
        True if valid, False otherwise
    """
    return api_key in VALID_API_KEYS


# ---------------------------------------------------------
# Authentication Dependencies
# ---------------------------------------------------------
async def get_current_user_jwt(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
) -> Optional[TokenData]:
    """
    Dependency that validates JWT bearer token.
    Returns None if no token provided (for optional auth).

    Raises:
        HTTPException: If token is provided but invalid
    """
    if credentials is None:
        return None

    token = credentials.credentials
    return verify_jwt_token(token)


async def get_current_user_api_key(
    api_key: Optional[str] = Security(api_key_header)
) -> Optional[str]:
    """
    Dependency that validates API key.
    Returns None if no API key provided (for optional auth).

    Raises:
        HTTPException: If API key is provided but invalid
    """
    if api_key is None:
        return None

    if not verify_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


async def require_authentication(
    jwt_user: Optional[TokenData] = Depends(get_current_user_jwt),
    api_key: Optional[str] = Depends(get_current_user_api_key)
) -> tuple[Optional[TokenData], Optional[str]]:
    """
    Dependency that requires EITHER JWT or API key authentication.
    Use this on endpoints that handle PHI or other sensitive operations.

    Returns:
        Tuple of (jwt_user, api_key) where one will be populated

    Raises:
        HTTPException: If neither authentication method is provided or both are invalid
    """
    if jwt_user is None and api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide either Bearer token or X-API-Key header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return jwt_user, api_key


async def optional_authentication(
    jwt_user: Optional[TokenData] = Depends(get_current_user_jwt),
    api_key: Optional[str] = Depends(get_current_user_api_key)
) -> tuple[Optional[TokenData], Optional[str]]:
    """
    Dependency that allows optional authentication.
    Use this on endpoints that can work with or without auth (e.g., rate limit differs).

    Returns:
        Tuple of (jwt_user, api_key) where both may be None
    """
    return jwt_user, api_key
