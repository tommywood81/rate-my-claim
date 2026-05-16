"""HTTP metadata for auth audit entries."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True, slots=True)
class AuthRequestContext:
    """Client metadata captured at auth boundaries."""

    ip_address: str | None
    user_agent: str | None
    correlation_id: str | None


def auth_context_from_request(request: Request) -> AuthRequestContext:
    """Build audit context from incoming request."""
    forwarded = request.headers.get("x-forwarded-for")
    ip = None
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    cid = getattr(request.state, "correlation_id", None)
    if not cid:
        cid = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
    return AuthRequestContext(
        ip_address=ip,
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
        correlation_id=cid,
    )
