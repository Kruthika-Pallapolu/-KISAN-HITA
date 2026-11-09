from typing import Optional
from fastapi import HTTPException, Request, status
from .database import consume_rate_limit


def enforce_rate_limit(request: Optional[Request], scope: str, limit: int, window_seconds: int = 60, identity: str | None = None) -> None:
    client = request.client.host if request is not None and request.client else "unknown"
    key = f"{scope}:{identity or client}"
    if not consume_rate_limit(key, limit, window_seconds):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again shortly.",
            headers={"Retry-After": str(window_seconds)},
        )
