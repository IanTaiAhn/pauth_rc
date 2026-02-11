"""
Rate limiting middleware for P-Auth RC.

Uses slowapi to implement token bucket rate limiting.
Different rate limits can be applied based on authentication status.
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
import os


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
# Default rate limits from environment or sensible defaults
DEFAULT_RATE_LIMIT = os.getenv("RATE_LIMIT_DEFAULT", "100/hour")
AUTHENTICATED_RATE_LIMIT = os.getenv("RATE_LIMIT_AUTHENTICATED", "1000/hour")


# ---------------------------------------------------------
# Rate Limiter Setup
# ---------------------------------------------------------
def get_identifier(request: Request) -> str:
    """
    Get identifier for rate limiting.

    Uses authenticated user ID if available, otherwise falls back to IP address.
    This allows authenticated users to have higher rate limits.

    Args:
        request: FastAPI request object

    Returns:
        Unique identifier string for rate limiting
    """
    # Check if user is authenticated (JWT or API key)
    # This assumes auth middleware has run and attached user info to request.state
    if hasattr(request.state, "user_id") and request.state.user_id:
        return f"user:{request.state.user_id}"

    if hasattr(request.state, "api_key") and request.state.api_key:
        return f"apikey:{request.state.api_key}"

    # Fall back to IP address for unauthenticated requests
    return get_remote_address(request)


# Create limiter instance
limiter = Limiter(
    key_func=get_identifier,
    default_limits=[DEFAULT_RATE_LIMIT],
    storage_uri=os.getenv("RATE_LIMIT_STORAGE_URI", "memory://"),
    # Can be changed to redis:// for distributed rate limiting in production
)


# ---------------------------------------------------------
# Rate Limit Decorators
# ---------------------------------------------------------
def rate_limit_default():
    """Apply default rate limit (for unauthenticated endpoints)."""
    return limiter.limit(DEFAULT_RATE_LIMIT)


def rate_limit_authenticated():
    """Apply higher rate limit for authenticated endpoints."""
    return limiter.limit(AUTHENTICATED_RATE_LIMIT)
