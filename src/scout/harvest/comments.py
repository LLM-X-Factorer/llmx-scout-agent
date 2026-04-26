"""Comment harvesting. Currently HN only — adapters live next to their sources."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

# very lightweight HN HTML -> text. HN comments contain <p>, <i>, <a>, <pre>, <code>.
_TAG_RE = re.compile(r"<[^>]+>")
_PARAGRAPH_RE = re.compile(r"</?p>", re.IGNORECASE)


def hn_html_to_text(s: str | None) -> str:
    if not s:
        return ""
    s = _PARAGRAPH_RE.sub("\n\n", s)
    s = _TAG_RE.sub("", s)
    return html.unescape(s).strip()


@dataclass
class CommentRecord:
    author: str
    text_md: str
    score: int | None  # HN comments don't expose score; field reserved for future sources

    def render(self) -> str:
        score_part = f"（{self.score} 分）" if self.score is not None else ""
        return f"### @{self.author}{score_part}\n\n{self.text_md}\n"
