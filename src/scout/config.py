"""Runtime configuration. Single source of truth for paths and thresholds."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


# Project root resolution: walks up to find pyproject.toml. Falls back to CWD.
def _find_project_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return cur


PROJECT_ROOT = _find_project_root(Path(__file__).parent)


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader. KEY=VALUE per line; # for comments. No quote handling
    (API keys don't need it). Existing env vars take precedence over the file
    (shell exports always win)."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# Load .env once at import so every entry point sees the same env.
_load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Config:
    project_root: Path
    output_dir: Path
    quarantine_dir: Path
    logs_dir: Path
    db_path: Path
    keywords_path: Path
    scoring_prompt_path: Path
    score_threshold: float = 7.0
    max_candidates_per_run: int = 50
    max_comments_per_pack: int = 5
    fulltext_max_chars: int = 50_000
    http_timeout_s: float = 20.0
    deliver_on_write: bool = True
    deliver_push: bool = True
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    user_agent: str = "llmx-scout-agent/0.1 (+https://github.com/LLM-X-Factorer/llmx-scout-agent)"
    extra: dict = field(default_factory=dict)


def load(toml_path: Path | None = None) -> Config:
    """Load config from config/scout.toml + env. Missing file is fine — we use defaults."""
    root = PROJECT_ROOT
    toml_path = toml_path or root / "config" / "scout.toml"
    raw: dict = {}
    if toml_path.exists():
        raw = tomllib.loads(toml_path.read_text())

    return Config(
        project_root=root,
        output_dir=root / raw.get("output_dir", "output/packs"),
        quarantine_dir=root / raw.get("quarantine_dir", "output/quarantine"),
        logs_dir=root / raw.get("logs_dir", "logs"),
        db_path=root / raw.get("db_path", "data/scout.sqlite"),
        keywords_path=root / raw.get("keywords_path", "config/keywords.txt"),
        scoring_prompt_path=root / raw.get("scoring_prompt_path", "prompts/scoring.md"),
        score_threshold=raw.get("score_threshold", 7.0),
        max_candidates_per_run=raw.get("max_candidates_per_run", 50),
        max_comments_per_pack=raw.get("max_comments_per_pack", 5),
        fulltext_max_chars=raw.get("fulltext_max_chars", 50_000),
        http_timeout_s=raw.get("http_timeout_s", 20.0),
        deliver_on_write=raw.get("deliver_on_write", True),
        deliver_push=raw.get("deliver_push", True),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        anthropic_model=raw.get("anthropic_model", "claude-sonnet-4-6"),
        user_agent=raw.get(
            "user_agent",
            "llmx-scout-agent/0.1 (+https://github.com/LLM-X-Factorer/llmx-scout-agent)",
        ),
        extra=raw,
    )
