"""Prompt calibration harness.

Reads YAML fixtures under `fixtures/calibration/`, runs the current scoring
prompt against each, compares the model's output with the human-supplied
`expected.*` fields, and reports per-fixture diffs and aggregate stats.

The aggregate stats are intentionally minimal: prompt calibration is a
human-in-the-loop activity, not a CI gate. The harness's job is to surface
disagreement; the human decides whether the prompt is wrong or the fixture is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from scout.filter.scoring import LLMClient, PromptBundle, score
from scout.models import Candidate, ScoreResult

Layer = Literal["引流层", "留存层", "转化层", "unsure"]


# ---- fixture schema ----


class FixtureInput(BaseModel):
    platform: str
    title: str
    primary_url: str
    original_url: str | None = None
    author: str | None = None
    matched_keywords: list[str] = Field(default_factory=list)
    metrics: dict[str, int | None] = Field(default_factory=dict)
    snippet: str | None = None
    comments_preview: str | None = None


class FixtureExpected(BaseModel):
    final_score: float
    layer: Layer
    judgment_seed_keywords: list[str] = Field(default_factory=list)

    @field_validator("final_score")
    @classmethod
    def _range(cls, v: float) -> float:
        if not (0.0 <= v <= 10.0):
            raise ValueError("expected.final_score must be in [0, 10]")
        return v


class FixtureTolerance(BaseModel):
    score: float = 1.5
    layer_strict: bool = False


class Fixture(BaseModel):
    id: str
    description: str = ""
    input: FixtureInput
    expected: FixtureExpected
    tolerance: FixtureTolerance = Field(default_factory=FixtureTolerance)
    notes: str = ""


def load_fixtures(directory: Path) -> list[Fixture]:
    """Load all *.yaml fixtures from a directory, sorted by filename."""
    out: list[Fixture] = []
    for f in sorted(directory.glob("*.yaml")):
        if f.name.lower() == "readme.md":
            continue
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        out.append(Fixture(**data))
    return out


# ---- running ----


def fixture_to_candidate(fx: Fixture) -> Candidate:
    """Build a Candidate suitable for scoring. URL hash is irrelevant here."""
    inp = fx.input
    return Candidate(
        source_platform=inp.platform,  # type: ignore[arg-type]
        external_id=fx.id,
        primary_url=inp.primary_url,
        original_url=inp.original_url or inp.primary_url,
        url_hash=f"fixture:{fx.id}",
        title=inp.title,
        snippet=inp.snippet,
        author=inp.author,
        metrics=inp.metrics,
        matched_keywords=inp.matched_keywords,
    )


# ---- diffing ----

Verdict = Literal["match", "score_off", "layer_off", "seed_off", "multi"]


@dataclass
class FixtureDiff:
    fixture: Fixture
    actual: ScoreResult
    score_delta: float
    score_within_tolerance: bool
    layer_match: bool
    seed_match: bool  # True if no keywords required, OR any keyword found in seed
    verdict: Verdict
    failures: list[str] = field(default_factory=list)


def diff(fx: Fixture, actual: ScoreResult) -> FixtureDiff:
    failures: list[str] = []

    delta = actual.final_score - fx.expected.final_score
    score_ok = abs(delta) <= fx.tolerance.score
    if not score_ok:
        failures.append(f"score off by {delta:+.1f} (tolerance ±{fx.tolerance.score})")

    layer_ok = actual.suggested_layer == fx.expected.layer
    if not layer_ok and fx.tolerance.layer_strict:
        failures.append(f"layer {actual.suggested_layer!r} != expected {fx.expected.layer!r}")

    seed_match = True
    required = fx.expected.judgment_seed_keywords
    if required:
        seed_lower = (actual.judgment_seed or "").lower()
        seed_match = any(kw.lower() in seed_lower for kw in required)
        if not seed_match:
            failures.append(f"seed missing all of {required}")

    if not failures:
        verdict: Verdict = "match"
    elif len(failures) > 1:
        verdict = "multi"
    elif not score_ok:
        verdict = "score_off"
    elif not layer_ok:
        verdict = "layer_off"
    else:
        verdict = "seed_off"

    return FixtureDiff(
        fixture=fx,
        actual=actual,
        score_delta=delta,
        score_within_tolerance=score_ok,
        layer_match=layer_ok,
        seed_match=seed_match,
        verdict=verdict,
        failures=failures,
    )


# ---- one-shot driver ----


@dataclass
class CalibrationReport:
    diffs: list[FixtureDiff]
    prompt_version: str
    prompt_model: str

    @property
    def total(self) -> int:
        return len(self.diffs)

    @property
    def matches(self) -> int:
        return sum(1 for d in self.diffs if d.verdict == "match")

    @property
    def mean_abs_delta(self) -> float:
        if not self.diffs:
            return 0.0
        return sum(abs(d.score_delta) for d in self.diffs) / len(self.diffs)

    @property
    def max_abs_delta(self) -> float:
        return max((abs(d.score_delta) for d in self.diffs), default=0.0)


def run(
    fixtures: list[Fixture], *, prompt: PromptBundle, client: LLMClient
) -> CalibrationReport:
    diffs: list[FixtureDiff] = []
    for fx in fixtures:
        cand = fixture_to_candidate(fx)
        actual = score(
            cand,
            prompt=prompt,
            client=client,
            comments_preview=fx.input.comments_preview or "",
        )
        diffs.append(diff(fx, actual))
    return CalibrationReport(diffs=diffs, prompt_version=prompt.version, prompt_model=prompt.model)
