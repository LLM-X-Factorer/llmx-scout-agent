"""Pydantic models matching docs/source-pack-schema.md v1.0."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0"

Platform = Literal[
    "hacker_news", "github", "reddit", "x", "product_hunt", "zhihu", "weibo", "manual", "other"
]
Layer = Literal["引流层", "留存层", "转化层", "unsure"]
ControversyType = Literal[
    "controversy",
    "counterintuitive_data",
    "underdog_story",
    "practical_contradiction",
    "expert_disagreement",
    "other",
]
FulltextMethod = Literal["trafilatura", "readability", "playwright", "api", "manual", "failed"]


class ControversySignal(BaseModel):
    type: ControversyType
    evidence: str
    url: str | None = None


class Source(BaseModel):
    platform: Platform
    primary_url: str
    original_url: str
    title: str
    author: str | None = None
    published_at: datetime | None = None
    language: str = "en"


class Metrics(BaseModel):
    model_config = ConfigDict(extra="allow")

    hn_score: int | None = None
    hn_comments: int | None = None
    github_stars: int | None = None
    github_stars_today: int | None = None
    reddit_upvotes: int | None = None
    reddit_comments: int | None = None
    x_likes: int | None = None
    x_reposts: int | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> Metrics:
        if not any(v is not None for v in self.model_dump().values()):
            raise ValueError("metrics must have at least one non-null field")
        return self


class ScoutAnalysis(BaseModel):
    matched_keywords: list[str] = Field(default_factory=list)
    llm_score: float | None = None
    llm_reasoning: str | None = None
    judgment_seed: str | None = None
    suggested_layer: Layer | None = None
    controversy_signals: list[ControversySignal] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("llm_score")
    @classmethod
    def _score_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 10.0):
            raise ValueError("llm_score must be in [0, 10]")
        return v


class Harvest(BaseModel):
    harvested_at: datetime
    fulltext_extracted: bool
    fulltext_method: FulltextMethod
    fulltext_external_file: str | None = None
    comments_count_fetched: int = 0
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _failure_must_warn(self) -> Harvest:
        if not self.fulltext_extracted and not self.warnings:
            raise ValueError("fulltext_extracted=false requires non-empty warnings")
        return self


class PackFrontmatter(BaseModel):
    """The YAML frontmatter portion of a source pack."""

    schema_version: str = SCHEMA_VERSION
    pack_id: str
    created_at: datetime
    created_by: str
    source: Source
    metrics: Metrics
    scout_analysis: ScoutAnalysis
    harvest: Harvest

    @field_validator("schema_version")
    @classmethod
    def _major_compat(cls, v: str) -> str:
        if not v.startswith("1."):
            raise ValueError(f"unsupported schema_version {v}; this build supports 1.x")
        return v


class Pack(BaseModel):
    """Frontmatter + body. The body is markdown rendered downstream."""

    frontmatter: PackFrontmatter
    body_markdown: str


# ----- Internal pipeline models (not part of the on-disk schema) -----


class Candidate(BaseModel):
    """In-flight item passed between pipeline stages."""

    source_platform: Platform
    external_id: str
    primary_url: str
    original_url: str
    url_hash: str
    title: str
    snippet: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    language: str = "en"
    metrics: dict[str, int | None] = Field(default_factory=dict)

    matched_keywords: list[str] = Field(default_factory=list)
    keyword_groups: list[str] = Field(default_factory=list)
    keyword_score: int = 0

    llm_score: float | None = None
    llm_reasoning: str | None = None
    judgment_seed: str | None = None
    suggested_layer: Layer | None = None
    controversy_signals: list[ControversySignal] = Field(default_factory=list)


class ScoreResult(BaseModel):
    """Output of the LLM scoring stage."""

    judgment_space: float
    controversy: float
    info_density: float
    final_score: float
    judgment_seed: str
    suggested_layer: Layer
    controversy_signals: list[ControversySignal]
    reasoning: str
    prompt_version: str
