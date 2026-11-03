"""In-memory smart read-through cache with write-through invalidation (Zero-Lag Pattern).

Ensures 100% of mutations and persistence hit the real Supabase PostgreSQL database,
while reads (Priority Queue, Case Drawers, Metrics, Approvals) return in sub-milliseconds.
"""
import time
from typing import Any

_CACHE: dict[str, tuple[float, Any]] = {}
_SANDBOX_VERSIONS: dict[str, int] = {}
_TOKEN_TO_SANDBOX: dict[str, tuple[float, str]] = {}


def get_sandbox_version(sandbox_id: str) -> int:
    """Return the monotonically increasing version number for this sandbox."""
    return _SANDBOX_VERSIONS.get(sandbox_id, 0)


def invalidate_sandbox_cache(sandbox_id: str) -> None:
    """Increment the sandbox cache version so all cached reads are instantly refreshed."""
    _SANDBOX_VERSIONS[sandbox_id] = _SANDBOX_VERSIONS.get(sandbox_id, 0) + 1


def get_cached(sandbox_id: str, key: str) -> Any | None:
    """Return cached response payload if valid and matching the current sandbox version."""
    v = get_sandbox_version(sandbox_id)
    cache_key = f"{sandbox_id}:v{v}:{key}"
    entry = _CACHE.get(cache_key)
    if entry is None:
        return None
    expires_at, val = entry
    if time.time() > expires_at:
        _CACHE.pop(cache_key, None)
        return None
    return val


def set_cached(sandbox_id: str, key: str, value: Any, ttl_seconds: float = 300.0) -> None:
    """Store response payload in memory with a default 5-minute TTL."""
    v = get_sandbox_version(sandbox_id)
    cache_key = f"{sandbox_id}:v{v}:{key}"
    _CACHE[cache_key] = (time.time() + ttl_seconds, value)
    # Periodically clean up very old entries if cache grows
    if len(_CACHE) > 500:
        now = time.time()
        for k in list(_CACHE.keys())[:100]:
            if _CACHE[k][0] < now:
                _CACHE.pop(k, None)


def get_cached_token_sandbox_id(token_hash: str) -> str | None:
    """Check if token_hash has recently been verified (avoids roundtrip on every HTTP request)."""
    entry = _TOKEN_TO_SANDBOX.get(token_hash)
    if entry is None:
        return None
    expires_at, s_id = entry
    if time.time() > expires_at:
        _TOKEN_TO_SANDBOX.pop(token_hash, None)
        return None
    return s_id


def set_cached_token_sandbox_id(
    token_hash: str, sandbox_id: str, ttl_seconds: float = 120.0
) -> None:
    """Cache verified token_hash -> sandbox_id mapping for 2 minutes."""
    _TOKEN_TO_SANDBOX[token_hash] = (time.time() + ttl_seconds, sandbox_id)
