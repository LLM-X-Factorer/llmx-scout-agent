"""Hacker News source via the public Firebase API.

Docs: https://github.com/HackerNews/API
No auth, no rate limit headers; we self-throttle with a small sleep.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import httpx

from scout.models import Candidate
from scout.utils.url_norm import canonicalize, url_hash

API = "https://hacker-news.firebaseio.com/v0"


class HackerNewsSource:
    name = "hacker_news"

    def __init__(self, *, client: httpx.Client, throttle_s: float = 0.05) -> None:
        self._client = client
        self._throttle = throttle_s

    def _get(self, path: str) -> dict | list | None:
        r = self._client.get(f"{API}/{path}")
        r.raise_for_status()
        if self._throttle:
            time.sleep(self._throttle)
        return r.json()

    def discover(self, limit: int) -> list[Candidate]:
        ids = self._get("topstories.json") or []
        ids = ids[: max(limit, 0)]
        out: list[Candidate] = []
        for item_id in ids:
            item = self._get(f"item/{item_id}.json")
            if not item or item.get("type") != "story" or item.get("dead") or item.get("deleted"):
                continue
            cand = self._to_candidate(item)
            if cand is not None:
                out.append(cand)
        return out

    def fetch_item(self, item_id: int) -> dict | None:
        data = self._get(f"item/{item_id}.json")
        return data if isinstance(data, dict) else None

    def fetch_top_comments(self, item: dict, limit: int) -> list[dict]:
        """Return top-N children, fully fetched, sorted by score descending.

        HN doesn't expose comment scores, so we keep the platform's order
        (which is by ranking algorithm — already a reasonable proxy for "top").
        """
        kids = item.get("kids") or []
        out: list[dict] = []
        for kid_id in kids[: max(limit * 2, limit)]:
            child = self.fetch_item(kid_id)
            if not child or child.get("dead") or child.get("deleted"):
                continue
            out.append(child)
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _to_candidate(item: dict) -> Candidate | None:
        item_id = item.get("id")
        if item_id is None:
            return None
        title = item.get("title") or ""
        url = item.get("url") or f"https://news.ycombinator.com/item?id={item_id}"
        primary = f"https://news.ycombinator.com/item?id={item_id}"
        original = url
        ts = item.get("time")
        published = datetime.fromtimestamp(ts, tz=UTC) if ts else None
        return Candidate(
            source_platform="hacker_news",
            external_id=str(item_id),
            primary_url=canonicalize(primary),
            original_url=canonicalize(original),
            url_hash=url_hash(original),
            title=title,
            snippet=item.get("text") or None,
            author=item.get("by"),
            published_at=published,
            language="en",
            metrics={
                "hn_score": item.get("score"),
                "hn_comments": item.get("descendants"),
            },
        )
