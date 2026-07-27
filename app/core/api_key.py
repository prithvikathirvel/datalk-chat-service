"""Helpers for generating and validating embed widget API keys.

Mirrors the behaviour described in the "Embed API Key Management" plan:

* ``generate_api_key`` returns a brand new key. The ``raw`` value is shown to
  the caller exactly once (at creation / rotation time) and is never
  persisted. Only the SHA-256 ``hash`` of the key is stored in the
  ``api_keys`` table, alongside a short ``prefix`` that is safe to display in
  the UI (e.g. ``dk_live_a1b2c3``).
* ``hash_api_key`` re-hashes a raw key supplied by a caller (widget / script)
  so it can be looked up against the stored hash.
"""

from __future__ import annotations

import base64
import hashlib
import secrets

API_KEY_PREFIX = "dk_live_"
API_KEY_RANDOM_BYTES = 32
API_KEY_DISPLAY_PREFIX_LEN = 12


def _b64url(data: bytes) -> str:
    """Base64url-encode ``data`` without padding (mirrors JS base64url)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def hash_api_key(raw_key: str) -> str:
    """Return the hex-encoded SHA-256 hash of ``raw_key``."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> dict:
    """Generate a new scoped API key.

    Returns a dict with:
        raw    -> the full key, e.g. "dk_live_aB3xQp7mNwRtYu9vKs2dFe6hCjLnOiPqZ4bGcM8W"
                  Shown to the caller ONCE. Never stored.
        hash   -> SHA-256(raw) hex digest. Stored in DB for lookup.
        prefix -> first N chars of raw, safe to store/display in UI.
    """
    raw = API_KEY_PREFIX + _b64url(secrets.token_bytes(API_KEY_RANDOM_BYTES))
    return {
        "raw": raw,
        "hash": hash_api_key(raw),
        "prefix": raw[:API_KEY_DISPLAY_PREFIX_LEN],
    }
