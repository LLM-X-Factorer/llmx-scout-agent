"""Assemble a Pack: validate the frontmatter via pydantic, write Markdown to disk."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from scout import __version__ as scout_version
from scout.models import (
    Candidate,
    Harvest,
    Metrics,
    Pack,
    PackFrontmatter,
    ScoreResult,
    ScoutAnalysis,
    Source,
)
from scout.utils.slug import slugify


def build_pack_id(candidate: Candidate, *, today: datetime, suffix: str | None = None) -> str:
    base = f"{candidate.source_platform.replace('_', '-')}-{today:%Y-%m-%d}-{candidate.external_id}"
    return f"{base}-{suffix}" if suffix else base


def assemble(
    candidate: Candidate,
    *,
    fulltext_md: str | None,
    fulltext_method: str,
    fulltext_warnings: list[str],
    comments_render: str,
    comments_count: int,
    score: ScoreResult | None,
    created_by: str = f"llmx-scout-agent@{scout_version}",
    pack_id_suffix: str | None = None,
    fulltext_external_file: str | None = None,
) -> Pack:
    now = datetime.now(UTC)
    metrics = Metrics(**candidate.metrics)
    analysis = ScoutAnalysis(
        matched_keywords=candidate.matched_keywords,
        llm_score=score.final_score if score else None,
        llm_reasoning=score.reasoning if score else None,
        judgment_seed=score.judgment_seed if score else None,
        suggested_layer=score.suggested_layer if score else None,
        controversy_signals=score.controversy_signals if score else [],
    )
    harvest = Harvest(
        harvested_at=now,
        fulltext_extracted=bool(fulltext_md),
        fulltext_method=fulltext_method,  # type: ignore[arg-type]
        fulltext_external_file=fulltext_external_file,
        comments_count_fetched=comments_count,
        warnings=fulltext_warnings,
    )
    fm = PackFrontmatter(
        pack_id=build_pack_id(candidate, today=now, suffix=pack_id_suffix),
        created_at=now,
        created_by=created_by,
        source=Source(
            platform=candidate.source_platform,
            primary_url=candidate.primary_url,
            original_url=candidate.original_url,
            title=candidate.title,
            author=candidate.author,
            published_at=candidate.published_at,
            language=candidate.language,
        ),
        metrics=metrics,
        scout_analysis=analysis,
        harvest=harvest,
    )
    body = _render_body(fm, fulltext_md=fulltext_md, comments_render=comments_render, score=score)
    return Pack(frontmatter=fm, body_markdown=body)


def _render_body(
    fm: PackFrontmatter, *, fulltext_md: str | None, comments_render: str, score: ScoreResult | None
) -> str:
    src = fm.source
    metrics_summary = ", ".join(
        f"{k.replace('_', ' ')} {v}" for k, v in fm.metrics.model_dump().items() if v is not None
    )
    parts: list[str] = []
    parts.append(f"# {src.title}\n")
    parts.append("## 来源元信息\n")
    parts.append(f"- **平台**：{src.platform}（[primary]({src.primary_url})）")
    parts.append(f"- **原文**：{src.original_url}")
    if src.author:
        published = src.published_at.date().isoformat() if src.published_at else ""
        parts.append(f"- **作者**：{src.author}{' · ' + published if published else ''}")
    parts.append(f"- **热度**：{metrics_summary or '（无）'}\n")

    parts.append("## Scout 的预判\n")
    parts.append(
        "> ⚠️ 以下为 scout 阶段的初步判断，下游 advocate-agent 应当校验、深化或推翻，"
        "不可直接采用。\n"
    )
    seed = (score.judgment_seed if score else "") or "（未生成）"
    layer = (score.suggested_layer if score else None) or "unsure"
    parts.append(f"**判断种子**：{seed}\n")
    parts.append(f"**建议层级**：{layer}\n")
    if score and score.controversy_signals:
        parts.append("**争议信号**：")
        for sig in score.controversy_signals:
            link = f"（[来源]({sig.url})）" if sig.url else ""
            parts.append(f"- {sig.type}：{sig.evidence}{link}")
        parts.append("")

    parts.append("## 原文正文\n")
    parts.append(
        fulltext_md.strip() if fulltext_md else "（抓取失败，详见 frontmatter.harvest.warnings）"
    )
    parts.append("")

    parts.append("## 评论区精华\n")
    parts.append(comments_render.strip() if comments_render.strip() else "（无评论）")
    return "\n".join(parts).rstrip() + "\n"


# ---- on-disk format ----


def to_markdown(pack: Pack) -> str:
    fm_dict = pack.frontmatter.model_dump(mode="json", exclude_none=False)
    fm_yaml = yaml.safe_dump(fm_dict, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{fm_yaml}\n---\n\n{pack.body_markdown}"


def write_pack(pack: Pack, *, output_dir: Path) -> Path:
    fm = pack.frontmatter
    date_dir = output_dir / fm.created_at.strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(fm.source.title)
    path = (
        date_dir / f"{slug}-{fm.source.platform.replace('_', '-')}-{fm.pack_id.split('-')[-1]}.md"
    )
    path.write_text(to_markdown(pack), encoding="utf-8")
    return path
