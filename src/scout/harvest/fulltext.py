"""Fulltext extraction. Trafilatura first, future fallbacks added on demand."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx
import trafilatura

Method = Literal["trafilatura", "readability", "playwright", "failed"]


@dataclass
class Extraction:
    text: str | None
    method: Method
    warnings: list[str]


def extract(url: str, *, client: httpx.Client) -> Extraction:
    warnings: list[str] = []
    try:
        r = client.get(url, follow_redirects=True)
        if r.status_code >= 400:
            warnings.append(f"http {r.status_code} fetching {url}")
            return Extraction(None, "failed", warnings)
        body = r.text
    except httpx.HTTPError as e:
        warnings.append(f"network error fetching {url}: {e}")
        return Extraction(None, "failed", warnings)

    md = trafilatura.extract(
        body,
        url=url,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )
    if md and md.strip():
        return Extraction(md.strip(), "trafilatura", warnings)
    warnings.append("trafilatura returned empty result")
    return Extraction(None, "failed", warnings)
