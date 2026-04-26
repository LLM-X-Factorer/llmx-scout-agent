"""Source interface: every source returns a list of Candidate objects."""

from __future__ import annotations

from typing import Protocol

from scout.models import Candidate


class Source(Protocol):
    name: str

    def discover(self, limit: int) -> list[Candidate]: ...
