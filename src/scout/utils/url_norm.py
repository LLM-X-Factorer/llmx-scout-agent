"""URL canonicalisation for dedup."""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Tracking params that have no semantic meaning. Keep tight; do not strip
# anything that could change page identity.
_TRACKING_PREFIXES = ("utm_",)
_TRACKING_EXACT = {"ref", "ref_src", "ref_url", "source", "fbclid", "gclid", "mc_cid", "mc_eid"}


def _strip_tracking(query: str) -> str:
    pairs = parse_qsl(query, keep_blank_values=False)
    kept = [
        (k, v)
        for k, v in pairs
        if k not in _TRACKING_EXACT and not any(k.startswith(p) for p in _TRACKING_PREFIXES)
    ]
    return urlencode(kept)


def canonicalize(url: str) -> str:
    """Return a canonical form of the URL.

    Rules:
    - lowercase scheme and host, drop default ports
    - strip leading 'www.'
    - strip tracking query params
    - drop fragments (HN comment anchors etc.)
    - keep path case (some sites are case sensitive)
    """
    p = urlparse(url.strip())
    if not p.scheme:
        # treat as relative; refuse to canonicalize
        return url
    scheme = p.scheme.lower()
    host = (p.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    netloc = host
    if p.port and not (
        (scheme == "http" and p.port == 80) or (scheme == "https" and p.port == 443)
    ):
        netloc = f"{host}:{p.port}"
    query = _strip_tracking(p.query)
    return urlunparse((scheme, netloc, p.path or "/", "", query, ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(canonicalize(url).encode("utf-8")).hexdigest()
