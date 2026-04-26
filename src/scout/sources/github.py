"""GitHub Trending source.

GitHub has no official trending API; we scrape the public HTML page at
https://github.com/trending. The page structure has been stable for years.
If it ever changes, the parser fails open (returns []) — discover continues
with other sources, dedup table is unaffected.

Caching is left to the caller (cron runs at 6h+ intervals; no need to cache
within a process). HTTP throttling is unnecessary at one request per run.
"""

from __future__ import annotations

import re
from typing import Literal

import httpx
from lxml import html as lxml_html

from scout.models import Candidate
from scout.utils.url_norm import canonicalize, url_hash

TRENDING_URL = "https://github.com/trending"

_INT_RE = re.compile(r"\d[\d,]*")


def _to_int(text: str | None) -> int | None:
    """Parse '12,345' -> 12345; '1,139 stars today' -> 1139. Returns None on no match."""
    if not text:
        return None
    m = _INT_RE.search(text.replace("\xa0", " "))
    if not m:
        return None
    return int(m.group(0).replace(",", ""))


class GitHubTrendingSource:
    name = "github"

    def __init__(
        self,
        *,
        client: httpx.Client,
        since: Literal["daily", "weekly", "monthly"] = "daily",
    ) -> None:
        self._client = client
        self._since = since

    def discover(self, limit: int) -> list[Candidate]:
        r = self._client.get(TRENDING_URL, params={"since": self._since})
        r.raise_for_status()
        tree = lxml_html.fromstring(r.text)
        articles = tree.xpath("//article[contains(@class, 'Box-row')]")
        out: list[Candidate] = []
        for article in articles[:limit]:
            cand = self._parse_article(article)
            if cand is not None:
                out.append(cand)
        return out

    @staticmethod
    def _parse_article(article) -> Candidate | None:  # type: ignore[no-untyped-def]
        hrefs = article.xpath(".//h2/a/@href")
        if not hrefs:
            return None
        href = hrefs[0].strip()  # "/owner/repo"
        if not href.startswith("/") or href.count("/") < 2:
            return None
        owner_repo = href.lstrip("/")  # "owner/repo"
        owner, _, _repo = owner_repo.partition("/")
        url = f"https://github.com{href}"

        desc_parts = article.xpath(".//p[contains(@class, 'col-9')]//text()")
        description = " ".join("".join(desc_parts).split()) or None

        stars_text = "".join(article.xpath(".//a[contains(@href, '/stargazers')]//text()"))
        today_text = "".join(
            article.xpath(
                ".//span[contains(@class, 'd-inline-block') "
                "and contains(@class, 'float-sm-right')]//text()"
            )
        )

        canon = canonicalize(url)
        return Candidate(
            source_platform="github",
            external_id=owner_repo,
            primary_url=canon,
            original_url=canon,
            url_hash=url_hash(url),
            title=owner_repo if not description else f"{owner_repo} — {description[:120]}",
            snippet=description,
            author=owner,
            language="en",
            metrics={
                "github_stars": _to_int(stars_text),
                "github_stars_today": _to_int(today_text),
            },
        )
