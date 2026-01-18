"""Rate limiting middleware for Daylily API.

Provides configurable rate limiting with support for:
- Per-endpoint category limits (auth, read, write, admin)
- IP-based and user-based rate limiting
- Redis or in-memory storage
- Whitelisting for internal services
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from daylib.config import Settings, get_settings

LOGGER = logging.getLogger("daylily.rate_limiting")


@dataclass
class RateLimitState:
    """State for a single rate limit bucket."""
    tokens: float
    last_update: float


class InMemoryStorage:
    """In-memory rate limit storage using token bucket algorithm."""

    def __init__(self):
        self._buckets: Dict[str, RateLimitState] = {}
        self._lock_time: Dict[str, float] = {}

    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60,
    ) -> Tuple[bool, int, int, int]:
        """Check if request is within rate limit.
        
        Args:
            key: Unique identifier (IP, user ID, etc.)
            limit: Maximum requests per window
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (allowed, remaining, limit, reset_time)
        """
        now = time.time()
        bucket = self._buckets.get(key)

        if bucket is None:
            # Initialize new bucket with full tokens
            bucket = RateLimitState(tokens=float(limit), last_update=now)
            self._buckets[key] = bucket

        # Calculate tokens to add based on time elapsed
        elapsed = now - bucket.last_update
        refill_rate = limit / window_seconds
        bucket.tokens = min(float(limit), bucket.tokens + elapsed * refill_rate)
        bucket.last_update = now

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            remaining = int(bucket.tokens)
            reset_time = int(now + window_seconds)
            return True, remaining, limit, reset_time
        else:
            remaining = 0
            # Calculate when one token will be available
            tokens_needed = 1.0 - bucket.tokens
            reset_time = int(now + tokens_needed / refill_rate)
            return False, remaining, limit, reset_time

    def cleanup_old_buckets(self, max_age_seconds: int = 3600) -> int:
        """Remove old buckets to prevent memory growth.
        
        Returns number of buckets removed.
        """
        now = time.time()
        cutoff = now - max_age_seconds
        old_keys = [k for k, v in self._buckets.items() if v.last_update < cutoff]
        for key in old_keys:
            del self._buckets[key]
        return len(old_keys)


class RateLimitCategory:
    """Rate limit category identifiers."""
    AUTH = "auth"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


@dataclass
class RateLimiter:
    """Rate limiter with configurable limits per category."""

    settings: Settings = field(default_factory=get_settings)
    storage: InMemoryStorage = field(default_factory=InMemoryStorage)

    def get_limit_for_category(self, category: str) -> int:
        """Get rate limit for a specific category."""
        limits = {
            RateLimitCategory.AUTH: self.settings.rate_limit_auth_per_minute,
            RateLimitCategory.READ: self.settings.rate_limit_read_per_minute,
            RateLimitCategory.WRITE: self.settings.rate_limit_write_per_minute,
            RateLimitCategory.ADMIN: self.settings.rate_limit_admin_per_minute,
        }
        return limits.get(category, self.settings.rate_limit_read_per_minute)

    def get_identifier(self, request: Request, category: str) -> str:
        """Get rate limit identifier based on category.
        
        AUTH endpoints: use IP address
        Other endpoints: use user ID if authenticated, else IP
        """
        # Get client IP from headers (handle proxies)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        if category == RateLimitCategory.AUTH:
            return f"ip:{client_ip}"

        # Try to get user ID from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"

        return f"ip:{client_ip}"

    def check_rate_limit(
        self,
        request: Request,
        category: str,
    ) -> Tuple[bool, Dict[str, str]]:
        """Check rate limit and return headers.
        
        Returns:
            Tuple of (allowed, headers_dict)
        """
        if not self.settings.rate_limit_enabled:
            return True, {}

        identifier = self.get_identifier(request, category)
        
        # Check whitelist
        raw_id = identifier.split(":", 1)[1] if ":" in identifier else identifier
        if self.settings.is_rate_limit_whitelisted(raw_id):
            LOGGER.debug("Rate limit bypassed for whitelisted: %s", raw_id)
            return True, {}

        limit = self.get_limit_for_category(category)
        allowed, remaining, limit_val, reset_time = self.storage.check_rate_limit(
            key=f"{category}:{identifier}",
            limit=limit,
            window_seconds=60,
        )

        headers = {
            "X-RateLimit-Limit": str(limit_val),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
            "X-RateLimit-Category": category,
        }

        if not allowed:
            headers["Retry-After"] = str(max(1, reset_time - int(time.time())))
            LOGGER.warning(
                "Rate limit exceeded for %s (category=%s, limit=%d)",
                identifier, category, limit_val
            )

        return allowed, headers


def create_rate_limit_dependency(
    category: str,
    rate_limiter: Optional[RateLimiter] = None,
) -> Callable:
    """Create a FastAPI dependency for rate limiting.

    Args:
        category: Rate limit category (auth, read, write, admin)
        rate_limiter: Optional RateLimiter instance (creates default if None)

    Returns:
        FastAPI dependency function
    """
    limiter = rate_limiter or RateLimiter()

    async def rate_limit_check(request: Request):
        allowed, headers = limiter.check_rate_limit(request, category)

        # Store headers in request state for middleware to add to response
        request.state.rate_limit_headers = headers

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"Too many requests. Limit: {headers['X-RateLimit-Limit']}/minute",
                    "retry_after": int(headers.get("Retry-After", 60)),
                },
                headers=headers,
            )

    return rate_limit_check


class RateLimitMiddleware:
    """Middleware to add rate limit headers to all responses."""

    def __init__(self, app, rate_limiter: Optional[RateLimiter] = None):
        self.app = app
        self.rate_limiter = rate_limiter

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                # Check if we have rate limit headers to add
                # (set by endpoint dependencies)
                request = Request(scope)
                rate_headers = getattr(request.state, "rate_limit_headers", {})

                if rate_headers:
                    # Convert existing headers to list
                    headers = list(message.get("headers", []))
                    for name, value in rate_headers.items():
                        headers.append((name.lower().encode(), str(value).encode()))
                    message = {**message, "headers": headers}

            await send(message)

        await self.app(scope, receive, send_with_headers)


# Convenience dependencies for common categories
rate_limit_auth = create_rate_limit_dependency(RateLimitCategory.AUTH)
rate_limit_read = create_rate_limit_dependency(RateLimitCategory.READ)
rate_limit_write = create_rate_limit_dependency(RateLimitCategory.WRITE)
rate_limit_admin = create_rate_limit_dependency(RateLimitCategory.ADMIN)

