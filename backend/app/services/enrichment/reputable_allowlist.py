"""Allowlisted publishers for enrichment source discovery."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import yaml

_BACKEND_DIR = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class AllowlistedPublisher:
    """Domain suffix or exact host with credibility score."""

    domain: str
    publisher: str
    credibility: float


def _resolve_allowlist_path(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    env_override = os.environ.get("REPUTABLE_SOURCES_CONFIG", "").strip()
    if env_override:
        return Path(env_override).expanduser().resolve()
    return (_BACKEND_DIR / raw).resolve()


@lru_cache
def load_allowlisted_publishers(config_path: str) -> tuple[AllowlistedPublisher, ...]:
    """Load publisher allowlist from YAML."""
    path = _resolve_allowlist_path(config_path)
    if not path.is_file():
        return ()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return ()
    rows = raw.get("publishers") or []
    out: list[AllowlistedPublisher] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        domain = str(row.get("domain", "")).strip().lower()
        if not domain:
            continue
        out.append(
            AllowlistedPublisher(
                domain=domain,
                publisher=str(row.get("publisher") or domain),
                credibility=float(row.get("credibility", 0.5) or 0.5),
            )
        )
    return tuple(out)


def clear_allowlist_cache() -> None:
    load_allowlisted_publishers.cache_clear()


def hostname_for_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        return host[4:]
    return host


def match_allowlisted_publisher(
    url: str,
    allowlist: tuple[AllowlistedPublisher, ...],
) -> AllowlistedPublisher | None:
    """Return best matching allowlist entry for a URL hostname."""
    host = hostname_for_url(url)
    if not host:
        return None
    best: AllowlistedPublisher | None = None
    best_len = -1
    for entry in allowlist:
        domain = entry.domain.lower()
        if host == domain or host.endswith(f".{domain}"):
            if len(domain) > best_len:
                best = entry
                best_len = len(domain)
    return best


def is_allowlisted_url(url: str, allowlist: tuple[AllowlistedPublisher, ...]) -> bool:
    return match_allowlisted_publisher(url, allowlist) is not None
