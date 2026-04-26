"""End-to-end pack assembly + on-disk roundtrip."""

from __future__ import annotations

from pathlib import Path

import yaml

from scout.harvest.packer import assemble, to_markdown, write_pack
from scout.models import Candidate, ControversySignal, ScoreResult


def _candidate() -> Candidate:
    return Candidate(
        source_platform="hacker_news",
        external_id="42",
        primary_url="https://news.ycombinator.com/item?id=42",
        original_url="https://example.com/post",
        url_hash="hash42",
        title="The truth about RAG",
        author="alice",
        metrics={"hn_score": 100, "hn_comments": 30},
        matched_keywords=["RAG"],
    )


def _score() -> ScoreResult:
    return ScoreResult(
        judgment_space=8,
        controversy=7,
        info_density=8,
        final_score=7.7,
        judgment_seed="表面是 X 但其实 Y",
        suggested_layer="留存层",
        controversy_signals=[
            ControversySignal(type="expert_disagreement", evidence="people disagree")
        ],
        reasoning="solid analysis space",
        prompt_version="v0.1",
    )


def test_assemble_and_write_roundtrip(tmp_path: Path):
    pack = assemble(
        _candidate(),
        fulltext_md="# Body\n\nHello world",
        fulltext_method="trafilatura",
        fulltext_warnings=[],
        comments_render="### @bob\n\nnice post",
        comments_count=1,
        score=_score(),
    )
    path = write_pack(pack, output_dir=tmp_path)
    assert path.exists()
    text = path.read_text()
    assert text.startswith("---\n")

    fm_yaml, body = text.split("\n---\n", 1)
    fm = yaml.safe_load(fm_yaml.lstrip("-").strip())

    assert fm["schema_version"] == "1.0"
    assert fm["scout_analysis"]["llm_score"] == 7.7
    assert fm["scout_analysis"]["judgment_seed"] == "表面是 X 但其实 Y"
    assert fm["metrics"]["hn_score"] == 100
    assert "Hello world" in body
    assert "@bob" in body
    assert "下游 advocate-agent 应当校验" in body  # warning banner present


def test_assemble_without_score_marks_unsure(tmp_path: Path):
    pack = assemble(
        _candidate(),
        fulltext_md="body",
        fulltext_method="trafilatura",
        fulltext_warnings=[],
        comments_render="",
        comments_count=0,
        score=None,
        created_by="manual",
    )
    md = to_markdown(pack)
    assert "建议层级" in md
    assert "unsure" in md
    assert "（未生成）" in md  # no judgment_seed


def test_failed_fulltext_renders_warning(tmp_path: Path):
    pack = assemble(
        _candidate(),
        fulltext_md=None,
        fulltext_method="failed",
        fulltext_warnings=["http 403"],
        comments_render="",
        comments_count=0,
        score=_score(),
    )
    md = to_markdown(pack)
    assert "抓取失败" in md
    fm_yaml, _ = md.split("\n---\n", 1)
    fm = yaml.safe_load(fm_yaml.lstrip("-").strip())
    assert fm["harvest"]["fulltext_extracted"] is False
    assert fm["harvest"]["warnings"] == ["http 403"]
