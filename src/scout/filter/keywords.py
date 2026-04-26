"""Keyword DSL parser and matcher.

Syntax (subset of TrendRadar's frequency_words.txt):

    # comment
    [Group Name]      # group header; '+' / '!' rules apply within the group
    plain_word
    +must_word        # any group base word matched then must also match this
    !forbidden        # if matched anywhere in title/snippet, candidate is dropped
    /regex/i          # PCRE-ish regex; trailing 'i' means case-insensitive
    alias_target => Display Name
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_GROUP = "_default"


@dataclass
class Rule:
    raw: str
    pattern: re.Pattern
    display: str
    kind: str  # 'base' | 'must' | 'forbid'


@dataclass
class Group:
    name: str
    base: list[Rule] = field(default_factory=list)
    must: list[Rule] = field(default_factory=list)
    forbid: list[Rule] = field(default_factory=list)


@dataclass
class Keywords:
    groups: list[Group]

    def match(self, title: str, snippet: str | None = None) -> tuple[list[str], list[str], int]:
        """Return (matched_display_names, matched_groups, score).

        Score = count of base-rule hits across all groups (informational only).
        A candidate passes overall if any group is satisfied AND no forbid rule fires
        anywhere in the text.
        """
        text = f"{title}\n{snippet or ''}"

        # global forbid: any forbid in any group blocks the candidate
        for g in self.groups:
            for r in g.forbid:
                if r.pattern.search(text):
                    return ([], [], 0)

        matched_display: list[str] = []
        matched_groups: list[str] = []
        score = 0
        for g in self.groups:
            base_hits = [r for r in g.base if r.pattern.search(text)]
            if not base_hits:
                continue
            # all 'must' rules in the group must match
            if g.must and not all(r.pattern.search(text) for r in g.must):
                continue
            matched_groups.append(g.name)
            score += len(base_hits)
            matched_display.extend(r.display for r in base_hits)

        # de-dup display names while preserving order
        seen: set[str] = set()
        deduped = [n for n in matched_display if not (n in seen or seen.add(n))]
        return (deduped, matched_groups, score)


# ---- parser ----


_REGEX_RE = re.compile(r"^/(?P<body>.+)/(?P<flags>[ims]*)$")


def _compile(token: str) -> re.Pattern:
    """Compile a token into a regex.

    - '/...../flags' -> regex literal
    - otherwise -> word-boundary literal, case-insensitive by default
    """
    m = _REGEX_RE.match(token)
    if m:
        flags = 0
        if "i" in m.group("flags"):
            flags |= re.IGNORECASE
        if "m" in m.group("flags"):
            flags |= re.MULTILINE
        if "s" in m.group("flags"):
            flags |= re.DOTALL
        return re.compile(m.group("body"), flags)
    # Use word boundary when the token is purely word-character; otherwise just
    # escape literally (handles things like "GPT-5", "C++" gracefully).
    if re.fullmatch(r"\w+", token):
        return re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
    return re.compile(re.escape(token), re.IGNORECASE)


def _parse_line(line: str) -> tuple[str, str, str] | None:
    """Return (kind, token, display) or None if line is blank/comment/header."""
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if s.startswith("[") and s.endswith("]"):
        return ("group", s[1:-1].strip(), "")
    kind = "base"
    if s.startswith("+"):
        kind = "must"
        s = s[1:].strip()
    elif s.startswith("!"):
        kind = "forbid"
        s = s[1:].strip()
    display = s
    if "=>" in s:
        token, display = (p.strip() for p in s.split("=>", 1))
    else:
        token = s
    return (kind, token, display)


def parse(text: str) -> Keywords:
    groups: list[Group] = [Group(DEFAULT_GROUP)]
    current = groups[0]
    for raw_line in text.splitlines():
        parsed = _parse_line(raw_line)
        if parsed is None:
            continue
        kind, token, display = parsed
        if kind == "group":
            current = Group(token)
            groups.append(current)
            continue
        rule = Rule(raw=token, pattern=_compile(token), display=display or token, kind=kind)
        getattr(current, kind).append(rule)
    # Drop empty default group if user moved everything into named groups
    return Keywords(groups=[g for g in groups if g.base or g.must or g.forbid])


def load_file(path: Path) -> Keywords:
    return parse(path.read_text(encoding="utf-8"))
