"""Double-submit CSRF cookie for browser sessions."""

from __future__ import annotations

import secrets

from fastapi import Request, Response

from app.core.config import Settings

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

CSRF_EXEMPT_PREFIXES = (
    "/health",
    "/ready",
    "/metrics",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/refresh",
)


def generate_csrf_token() -> str:
    """Return a new CSRF secret."""
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str, settings: Settings) -> None:
    """Set readable CSRF cookie for double-submit validation."""
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
        domain=settings.cookie_domain,
    )


def clear_csrf_cookie(response: Response, settings: Settings) -> None:
    """Remove CSRF cookie on logout."""
    response.delete_cookie(settings.csrf_cookie_name, path="/", domain=settings.cookie_domain)


def _is_exempt(path: str) -> bool:
    return any(path == p or path.startswith(f"{p}/") for p in CSRF_EXEMPT_PREFIXES)


def _uses_bearer_only(request: Request) -> bool:
    auth = request.headers.get("authorization", "")
    return auth.lower().startswith("bearer ")


def csrf_check_required(request: Request) -> bool:
    """Whether this request must pass CSRF validation."""
    if request.method not in UNSAFE_METHODS:
        return False
    path = request.url.path
    if not path.startswith("/api/"):
        return False
    if _is_exempt(path):
        return False
    if _uses_bearer_only(request):
        return False
    return True


def validate_csrf(request: Request, settings: Settings) -> bool:
    """Compare header token to cookie."""
    cookie_val = request.cookies.get(settings.csrf_cookie_name)
    header_val = request.headers.get("x-csrf-token") or request.headers.get("X-CSRF-Token")
    if not cookie_val or not header_val:
        return False
    return secrets.compare_digest(cookie_val, header_val)
