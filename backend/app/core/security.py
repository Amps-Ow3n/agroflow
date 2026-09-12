import secrets
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status

from app.core.config import settings


class InMemoryRateLimiter:
    """Small-process limiter suitable for the Phase A pilot.

    Replace with a shared/distributed store before running multiple backend instances.
    """
    def __init__(self):
        self._events = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= window_seconds:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True


rate_limiter = InMemoryRateLimiter()


def client_key(request: Request, action: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{action}:{host}"


def enforce_rate_limit(request: Request, action: str):
    if action == "login":
        allowed = rate_limiter.allow(client_key(request, action), settings.RATE_LIMIT_LOGIN_MAX, settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS)
    else:
        allowed = rate_limiter.allow(client_key(request, action), settings.RATE_LIMIT_REGISTER_MAX, settings.RATE_LIMIT_REGISTER_WINDOW_SECONDS)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests. Please try again later.")


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def get_auth_token(request, header_token=None):
    """Return a bearer token when supplied, otherwise the session cookie token."""
    return header_token or request.cookies.get(settings.SESSION_COOKIE_NAME)
