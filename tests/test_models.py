from datetime import UTC, datetime

import pytest

from scout.models import (
    Harvest,
    Metrics,
    PackFrontmatter,
    ScoutAnalysis,
    Source,
)


def _ok_source() -> Source:
    return Source(
        platform="hacker_news",
        primary_url="https://news.ycombinator.com/item?id=1",
        original_url="https://example.com/x",
        title="Test",
    )


def test_metrics_requires_at_least_one_value():
    with pytest.raises(ValueError, match="at least one"):
        Metrics(hn_score=None, hn_comments=None)
    Metrics(hn_score=42)  # ok


def test_llm_score_range():
    ScoutAnalysis(llm_score=0.0)
    ScoutAnalysis(llm_score=10.0)
    with pytest.raises(ValueError):
        ScoutAnalysis(llm_score=10.1)
    with pytest.raises(ValueError):
        ScoutAnalysis(llm_score=-0.1)


def test_harvest_failure_must_warn():
    with pytest.raises(ValueError, match="warnings"):
        Harvest(
            harvested_at=datetime.now(UTC),
            fulltext_extracted=False,
            fulltext_method="failed",
            warnings=[],
        )
    Harvest(
        harvested_at=datetime.now(UTC),
        fulltext_extracted=False,
        fulltext_method="failed",
        warnings=["http 403"],
    )  # ok


def test_schema_version_rejects_v2():
    with pytest.raises(ValueError, match="schema_version"):
        PackFrontmatter(
            schema_version="2.0",
            pack_id="x",
            created_at=datetime.now(UTC),
            created_by="manual",
            source=_ok_source(),
            metrics=Metrics(hn_score=1),
            scout_analysis=ScoutAnalysis(),
            harvest=Harvest(
                harvested_at=datetime.now(UTC),
                fulltext_extracted=True,
                fulltext_method="trafilatura",
            ),
        )
