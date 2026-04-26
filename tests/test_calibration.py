"""Tests for the calibration harness — loader, diffing, aggregate stats."""

from __future__ import annotations

from pathlib import Path

import pytest

from scout.calibration import (
    Fixture,
    FixtureExpected,
    FixtureInput,
    FixtureTolerance,
    diff,
    fixture_to_candidate,
    load_fixtures,
    run,
)
from scout.filter.scoring import PromptBundle
from scout.models import ControversySignal, ScoreResult


def _fx(*, score: float, layer: str = "留存层", seed_kw: list[str] | None = None) -> Fixture:
    return Fixture(
        id="t",
        description="",
        input=FixtureInput(
            platform="hacker_news",
            title="Test",
            primary_url="https://example.com",
            metrics={"hn_score": 1},
        ),
        expected=FixtureExpected(
            final_score=score,
            layer=layer,  # type: ignore[arg-type]
            judgment_seed_keywords=seed_kw or [],
        ),
        tolerance=FixtureTolerance(score=1.5, layer_strict=False),
    )


def _result(*, score: float, layer: str = "留存层", seed: str = "X but Y") -> ScoreResult:
    return ScoreResult(
        judgment_space=score,
        controversy=score,
        info_density=score,
        final_score=score,
        judgment_seed=seed,
        suggested_layer=layer,  # type: ignore[arg-type]
        controversy_signals=[],
        reasoning="",
        prompt_version="v0.1",
    )


def test_diff_match_when_within_tolerance():
    d = diff(_fx(score=7.0), _result(score=7.5))
    assert d.verdict == "match"
    assert d.failures == []
    assert d.score_within_tolerance


def test_diff_score_off():
    d = diff(_fx(score=7.0), _result(score=4.0))
    assert d.verdict == "score_off"
    assert d.score_delta == pytest.approx(-3.0)
    assert "score off" in d.failures[0]


def test_diff_layer_off_only_when_strict():
    fx = _fx(score=7.0, layer="留存层")
    fx.tolerance.layer_strict = True
    d = diff(fx, _result(score=7.0, layer="引流层"))
    assert d.verdict == "layer_off"

    fx.tolerance.layer_strict = False
    d2 = diff(fx, _result(score=7.0, layer="引流层"))
    # Non-strict: layer mismatch noted but doesn't fail
    assert d2.verdict == "match"
    assert d2.layer_match is False


def test_diff_seed_keyword_required():
    fx = _fx(score=7.0, seed_kw=["数据飞轮"])
    d = diff(fx, _result(score=7.0, seed="表面是 X 但其实 Y"))
    assert d.verdict == "seed_off"
    assert "seed missing" in d.failures[0]

    d2 = diff(fx, _result(score=7.0, seed="表面是合规，实则数据飞轮"))
    assert d2.verdict == "match"


def test_diff_multi_failure_classified_as_multi():
    fx = _fx(score=7.0, seed_kw=["foo"])
    d = diff(fx, _result(score=2.0, seed="bar"))
    assert d.verdict == "multi"
    assert len(d.failures) == 2


def test_load_real_fixtures_dir():
    dir_ = Path(__file__).parent.parent / "fixtures" / "calibration"
    fixtures = load_fixtures(dir_)
    assert len(fixtures) >= 4
    ids = [f.id for f in fixtures]
    # Files use NNN- prefix → load order should match numeric order
    assert ids[:4] == [
        "erdos-chatgpt",            # 001-
        "openai-privacy-filter",    # 002-
        "eden-ai-alternative",      # 003-
        "datalog-gpu",              # 004-
    ]


def test_fixture_to_candidate_preserves_input():
    fx = _fx(score=7.0)
    cand = fixture_to_candidate(fx)
    assert cand.title == "Test"
    assert cand.url_hash.startswith("fixture:")
    assert cand.metrics == {"hn_score": 1}


# ---- harness end-to-end with fake LLM ----


class _FakeClient:
    def __init__(self, response_per_id: dict[str, str]) -> None:
        self.response_per_id = response_per_id
        self._call = 0

    def complete(self, *, model, system, user, temperature, max_tokens):
        # crude lookup by which fixture's title appears in the prompt
        for fid, body in self.response_per_id.items():
            if fid in user or any(piece in user for piece in [fid, fid.replace("-", " ")]):
                return body
        # default — returns garbage to make missing branches obvious
        self._call += 1
        return self.response_per_id.get("_default", "")


def _resp(score: float, seed: str, layer: str = "留存层") -> str:
    return (
        f'{{"scores":{{"judgment_space":{score},"controversy":{score},'
        f'"info_density":{score},"final_score":{score}}},'
        f'"judgment_seed":"{seed}","suggested_layer":"{layer}",'
        f'"controversy_signals":[],"reasoning":"r"}}'
    )


def test_run_returns_report_with_aggregates():
    fixtures = [
        _fx(score=7.0),
        _fx(score=7.0),
    ]
    fixtures[0].id = "f1"
    fixtures[0].input.title = "f1-marker"
    fixtures[1].id = "f2"
    fixtures[1].input.title = "f2-marker"

    client = _FakeClient(
        {
            "f1-marker": _resp(7.5, "X but Y"),
            "f2-marker": _resp(3.0, ""),
        }
    )
    prompt = PromptBundle(
        version="v0.1",
        model="fake",
        temperature=0.0,
        max_tokens=200,
        system="sys",
        user_template="title={{title}} kw={{matched_keywords}}",
    )
    report = run(fixtures, prompt=prompt, client=client)
    assert report.total == 2
    assert report.matches == 1  # first matches (Δ=0.5), second misses (Δ=-4.0)
    assert report.mean_abs_delta == pytest.approx((0.5 + 4.0) / 2)
    assert report.max_abs_delta == pytest.approx(4.0)


def test_signal_field_present_on_diff_dataclass():
    # Ensure ControversySignal stays optional / harmless if a fixture forgets it.
    d = diff(_fx(score=7.0), _result(score=7.5))
    assert d.actual.controversy_signals == [] or isinstance(
        d.actual.controversy_signals[0], ControversySignal
    )
