"""Reddit source via the public JSON endpoints.

No auth needed; Reddit blocks default httpx UA aggressively, so a descriptive
User-Agent is mandatory. We rely on `config.user_agent` (set on the shared
httpx client by cli._http()).

Subreddits to scan are configurable via config/scout.toml `reddit.subreddits`;
defaults are LocalLLaMA / MachineLearning / singularity per spec.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import httpx

from scout.models import Candidate
from scout.utils.url_norm import canonicalize, url_hash

DEFAULT_SUBREDDITS = ("LocalLLaMA", "MachineLearning", "singularity")
LISTING = "https://www.reddit.com/r/{subreddit}/hot.json"
COMMENTS = "https://www.reddit.com/comments/{post_id}.json"


class RedditSource:
    name = "reddit"

    def __init__(
        self,
        *,
        client: httpx.Client,
        subreddits: tuple[str, ...] = DEFAULT_SUBREDDITS,
        throttle_s: float = 1.0,
    ) -> None:
        self._client = client
        self._subreddits = subreddits
        # Reddit unauthenticated rate limit is ~60 req/min; one second between
        # subreddit listings is safe and never near the limit.
        self._throttle = throttle_s

    def discover(self, limit: int) -> list[Candidate]:
        """Fetch hot posts from each subreddit; flat list, deduped by url_hash."""
        per_sub = max(1, limit // max(1, len(self._subreddits)))
        seen: set[str] = set()
        out: list[Candidate] = []
        for sub in self._subreddits:
            for cand in self._fetch_subreddit(sub, per_sub):
                if cand.url_hash in seen:
                    continue
                seen.add(cand.url_hash)
                out.append(cand)
            if self._throttle:
                time.sleep(self._throttle)
        return out

    def _fetch_subreddit(self, subreddit: str, limit: int) -> list[Candidate]:
        r = self._client.get(LISTING.format(subreddit=subreddit), params={"limit": limit})
        r.raise_for_status()
        data = r.json()
        children = data.get("data", {}).get("children", [])
        out: list[Candidate] = []
        for ch in children:
            cand = self._to_candidate(ch.get("data", {}), subreddit)
            if cand is not None:
                out.append(cand)
        return out

    def fetch_top_comments(self, post_id: str, limit: int) -> list[dict]:
        """Top-level comments only, sorted by Reddit's default (best). Reply trees
        are flattened away — for the LLM preview we only need top-level voices."""
        r = self._client.get(COMMENTS.format(post_id=post_id), params={"limit": limit, "depth": 1})
        r.raise_for_status()
        data = r.json()
        # Reddit returns [post_listing, comments_listing]
        if not isinstance(data, list) or len(data) < 2:
            return []
        children = data[1].get("data", {}).get("children", [])
        out: list[dict] = []
        for ch in children:
            kind = ch.get("kind")
            cd = ch.get("data", {})
            if kind != "t1":  # t1 = comment; skip "more" placeholders
                continue
            if cd.get("removed_by_category") or cd.get("body") in (None, "[removed]", "[deleted]"):
                continue
            out.append(cd)
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _to_candidate(post: dict, subreddit: str) -> Candidate | None:
        post_id = post.get("id")
        title = post.get("title")
        if not post_id or not title:
            return None
        if post.get("removed_by_category") or post.get("over_18"):
            return None  # NSFW filter — not what scout's looking for
        permalink = post.get("permalink") or f"/r/{subreddit}/comments/{post_id}/"
        primary = f"https://www.reddit.com{permalink}"
        external = post.get("url") or primary
        # is_self == True means selfpost, external URL == primary
        if post.get("is_self"):
            external = primary
        ts = post.get("created_utc")
        published = datetime.fromtimestamp(ts, tz=UTC) if ts else None
        selftext = post.get("selftext") or None
        if selftext and len(selftext) > 1000:
            selftext = selftext[:1000] + "..."
        return Candidate(
            source_platform="reddit",
            external_id=str(post_id),
            primary_url=canonicalize(primary),
            original_url=canonicalize(external),
            url_hash=url_hash(external),
            title=title,
            snippet=selftext,
            author=post.get("author"),
            published_at=published,
            language="en",
            metrics={
                "reddit_upvotes": post.get("ups") or post.get("score"),
                "reddit_comments": post.get("num_comments"),
            },
        )
