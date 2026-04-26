"""Command-line entry point. `scout --help` for the menu."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import httpx
import typer

from scout import calibration as cal
from scout import config as cfg
from scout import models
from scout.filter import keywords as kw
from scout.filter import scoring as sc
from scout.harvest import comments as cmts
from scout.harvest import fulltext as ft
from scout.harvest import packer
from scout.sources.hacker_news import HackerNewsSource
from scout.store import db

app = typer.Typer(no_args_is_help=True, add_completion=False, help="llmx-scout-agent CLI")


# ---- shared wiring ----


def _http(c: cfg.Config) -> httpx.Client:
    return httpx.Client(
        timeout=c.http_timeout_s,
        headers={"User-Agent": c.user_agent},
        follow_redirects=True,
    )


def _llm_client(c: cfg.Config) -> sc.LLMClient:
    """Pick the LLM client.

    Defaults to Anthropic. Set SCOUT_LLM_PROVIDER=openrouter to use OpenRouter
    (development / testing only — the production design is Anthropic-only;
    see CLAUDE.md decision log).
    """
    provider = os.environ.get("SCOUT_LLM_PROVIDER", "anthropic").lower()
    if provider == "openrouter":
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise typer.BadParameter("OPENROUTER_API_KEY env var is not set")
        return sc.OpenRouterClient(key)
    if not c.anthropic_api_key:
        raise typer.BadParameter("ANTHROPIC_API_KEY env var is not set")
    return sc.AnthropicClient(c.anthropic_api_key)


def _hn_id_from_url(url: str) -> int | None:
    m = re.search(r"news\.ycombinator\.com/item\?id=(\d+)", url)
    return int(m.group(1)) if m else None


@dataclass
class HarvestResult:
    fulltext_md: str | None
    method: str
    warnings: list[str]
    comments: list[cmts.CommentRecord]

    @property
    def comments_render(self) -> str:
        return "\n".join(c.render() for c in self.comments)

    @property
    def comments_preview(self) -> str:
        """Short preview suitable for the LLM prompt (top 3, 200 chars each)."""
        bits = []
        for c in self.comments[:3]:
            snippet = c.text_md.replace("\n", " ")[:200]
            bits.append(f"- @{c.author}: {snippet}")
        return "\n".join(bits)


def _harvest_hn(item: dict, *, http: httpx.Client, c: cfg.Config) -> HarvestResult:
    hn = HackerNewsSource(client=http)
    target_url = item.get("url") or f"https://news.ycombinator.com/item?id={item['id']}"
    extr = ft.extract(target_url, client=http)
    raw_comments = hn.fetch_top_comments(item, c.max_comments_per_pack)
    records = [
        cmts.CommentRecord(
            author=cm.get("by") or "unknown",
            text_md=cmts.hn_html_to_text(cm.get("text")),
            score=None,
        )
        for cm in raw_comments
    ]
    return HarvestResult(extr.text, extr.method, extr.warnings, records)


def _build_candidate_from_hn_item(item: dict) -> models.Candidate:
    cand = HackerNewsSource._to_candidate(item)
    if cand is None:
        raise typer.BadParameter(f"HN item {item.get('id')} is not packable")
    return cand


def _persist(
    conn,
    *,
    candidate: models.Candidate,
    score: models.ScoreResult | None,
    pack_id: str | None,
    decision: db.Decision,
) -> None:
    now = datetime.now(UTC)
    db.upsert_dedup(
        conn,
        url_hash=candidate.url_hash,
        canonical_url=candidate.original_url,
        seen_at=now,
        metrics=candidate.metrics,
    )
    db.record_decision(
        conn,
        url_hash=candidate.url_hash,
        decision=decision,
        pack_id=pack_id,
        last_score=score.final_score if score else None,
    )
    if score is not None:
        db.append_score(
            conn,
            url_hash=candidate.url_hash,
            scored_at=now,
            prompt_version=score.prompt_version,
            score=score.final_score,
            payload={
                "title": candidate.title,
                "primary_url": candidate.primary_url,
                "matched_keywords": candidate.matched_keywords,
                "metrics": candidate.metrics,
                "scores": {
                    "judgment_space": score.judgment_space,
                    "controversy": score.controversy,
                    "info_density": score.info_density,
                    "final_score": score.final_score,
                },
                "judgment_seed": score.judgment_seed,
                "suggested_layer": score.suggested_layer,
                "reasoning": score.reasoning,
            },
        )


# ---- commands ----


@app.command()
def pack(
    url: Annotated[str, typer.Argument(help="URL to package (HN item URL or any article URL)")],
    note: Annotated[
        str | None, typer.Option(help="free-text note saved to scout_analysis.notes")
    ] = None,
    no_score: Annotated[
        bool, typer.Option("--no-score", help="skip LLM scoring (manual mode)")
    ] = False,
) -> None:
    """Manually package one URL. Skips Discover and keyword filter; still scores by default.

    HN item URLs are special-cased: we pull the item via the HN API to capture
    metrics and comments. Other URLs go through the generic fulltext path with
    no metrics — packaging will fail unless you set --no-score and metrics
    cannot be inferred (Metrics requires at least one non-null field).
    """
    c = cfg.load()
    http = _http(c)
    conn = db.connect(c.db_path)

    hn_id = _hn_id_from_url(url)
    if hn_id is None:
        typer.echo("non-HN URLs are not yet supported in this build", err=True)
        raise typer.Exit(2)

    hn = HackerNewsSource(client=http)
    item = hn.fetch_item(hn_id)
    if not item:
        typer.echo(f"HN item {hn_id} not found", err=True)
        raise typer.Exit(2)

    candidate = _build_candidate_from_hn_item(item)
    h = _harvest_hn(item, http=http, c=c)

    score: models.ScoreResult | None = None
    if not no_score:
        prompt = sc.load_prompt(c.scoring_prompt_path, model_override=os.environ.get("SCOUT_LLM_MODEL"))
        client = _llm_client(c)
        score = sc.score(
            candidate, prompt=prompt, client=client, comments_preview=h.comments_preview
        )

    assemble_kwargs = {}
    if no_score:
        assemble_kwargs["created_by"] = "manual"
    pack_obj = packer.assemble(
        candidate,
        fulltext_md=h.fulltext_md,
        fulltext_method=h.method,
        fulltext_warnings=h.warnings,
        comments_render=h.comments_render,
        comments_count=len(h.comments),
        score=score,
        **assemble_kwargs,
    )
    if note:
        pack_obj.frontmatter.scout_analysis.notes = note

    path = packer.write_pack(pack_obj, output_dir=c.output_dir)
    _persist(
        conn,
        candidate=candidate,
        score=score,
        pack_id=pack_obj.frontmatter.pack_id,
        decision="packed",
    )
    typer.echo(f"wrote {path.relative_to(c.project_root)}")


@app.command()
def discover(
    limit: Annotated[int, typer.Option(help="max items pulled per source")] = 30,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="don't write pack or hit LLM")] = False,
    sources: Annotated[
        list[str] | None,
        typer.Option("--source", help="restrict to source(s). default: all"),
    ] = None,
) -> None:
    """Run one full discover → filter → score → harvest → pack pass."""
    c = cfg.load()
    http = _http(c)
    conn = db.connect(c.db_path)
    keywords = kw.load_file(c.keywords_path)

    enabled = set(sources) if sources else {"hacker_news"}
    if "hacker_news" not in enabled:
        typer.echo("only hacker_news is wired up in this build", err=True)
        raise typer.Exit(2)

    hn = HackerNewsSource(client=http)
    typer.echo(f"discovering up to {limit} HN stories...")
    candidates = hn.discover(limit)
    typer.echo(f"got {len(candidates)} candidates")

    # Keyword filter — dry-run must not write anything to the db
    passed: list[tuple[models.Candidate, dict]] = []
    for cand in candidates:
        if db.get_dedup(conn, cand.url_hash) is not None:
            continue
        names, groups, score_count = keywords.match(cand.title, cand.snippet)
        if not names:
            if not dry_run:
                db.upsert_dedup(
                    conn,
                    url_hash=cand.url_hash,
                    canonical_url=cand.original_url,
                    seen_at=datetime.now(UTC),
                    metrics=cand.metrics,
                )
                db.record_decision(conn, url_hash=cand.url_hash, decision="filtered_out")
            continue
        cand.matched_keywords = names
        cand.keyword_groups = groups
        cand.keyword_score = score_count
        passed.append((cand, {"groups": groups}))
    typer.echo(f"keyword-passed: {len(passed)}")

    if not passed:
        return

    if dry_run:
        for cand, _ in passed:
            typer.echo(f"  [dry-run] {cand.matched_keywords}: {cand.title}")
        return

    prompt = sc.load_prompt(c.scoring_prompt_path, model_override=os.environ.get("SCOUT_LLM_MODEL"))
    client = _llm_client(c)
    written = 0
    for cand, _ in passed[: c.max_candidates_per_run]:
        # Prefetch a small comment preview so the scorer has real signal beyond
        # the title. HN top stories rarely have a `text` body, so without this
        # the LLM scores blind. Cost: 1 fetch_item + 3 fetch_item calls per
        # keyword-passed candidate (HN's API is uncapped and self-throttled).
        item = hn.fetch_item(int(cand.external_id))
        if not item:
            typer.echo(f"  ! HN item vanished: {cand.external_id}", err=True)
            continue
        preview_records = [
            cmts.CommentRecord(
                author=cm.get("by") or "unknown",
                text_md=cmts.hn_html_to_text(cm.get("text")),
                score=None,
            )
            for cm in hn.fetch_top_comments(item, 3)
        ]
        comments_preview = "\n".join(
            f"- @{r.author}: {r.text_md.replace(chr(10), ' ')[:200]}" for r in preview_records
        )

        try:
            score = sc.score(cand, prompt=prompt, client=client, comments_preview=comments_preview)
        except Exception as e:
            typer.echo(f"  ! scoring failed for {cand.title!r}: {e}", err=True)
            db.upsert_dedup(
                conn,
                url_hash=cand.url_hash,
                canonical_url=cand.original_url,
                seen_at=datetime.now(UTC),
                metrics=cand.metrics,
            )
            db.record_decision(conn, url_hash=cand.url_hash, decision="failed")
            continue

        if score.final_score < c.score_threshold:
            typer.echo(f"  · low {score.final_score:.1f}: {cand.title}")
            _persist(conn, candidate=cand, score=score, pack_id=None, decision="low_score")
            continue

        # Threshold passed — full harvest (we already have the item)
        h = _harvest_hn(item, http=http, c=c)
        pack_obj = packer.assemble(
            cand,
            fulltext_md=h.fulltext_md,
            fulltext_method=h.method,
            fulltext_warnings=h.warnings,
            comments_render=h.comments_render,
            comments_count=len(h.comments),
            score=score,
        )
        path = packer.write_pack(pack_obj, output_dir=c.output_dir)
        _persist(
            conn,
            candidate=cand,
            score=score,
            pack_id=pack_obj.frontmatter.pack_id,
            decision="packed",
        )
        typer.echo(f"  ✓ {score.final_score:.1f}: {path.relative_to(c.project_root)}")
        written += 1

    typer.echo(f"done: wrote {written} pack(s)")


@app.command(name="list")
def list_packs(
    since: Annotated[str | None, typer.Option(help="YYYY-MM-DD; default = past 7 days")] = None,
) -> None:
    """List recent pack files."""
    c = cfg.load()
    if not c.output_dir.exists():
        typer.echo("(no packs yet)")
        return
    cutoff = None
    if since:
        cutoff = datetime.fromisoformat(since).date()
    for date_dir in sorted(c.output_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        try:
            d = datetime.fromisoformat(date_dir.name).date()
        except ValueError:
            continue
        if cutoff and d < cutoff:
            continue
        for f in sorted(date_dir.iterdir()):
            if f.suffix == ".md":
                typer.echo(str(f.relative_to(c.project_root)))


@app.command()
def show(pack_id: Annotated[str, typer.Argument()]) -> None:
    """Print a pack's frontmatter + body."""
    c = cfg.load()
    if not c.output_dir.exists():
        typer.echo("(no packs)")
        raise typer.Exit(1)
    for f in c.output_dir.rglob("*.md"):
        if pack_id in f.read_text(encoding="utf-8")[:2000]:
            typer.echo(f.read_text(encoding="utf-8"))
            return
    typer.echo(f"pack {pack_id} not found", err=True)
    raise typer.Exit(1)


_VERDICT_MARK = {
    "match": "✓",
    "score_off": "≠",
    "layer_off": "L",
    "seed_off": "S",
    "multi": "✗",
}


@app.command(name="score-tune")
def score_tune(
    fixtures_dir: Annotated[
        Path | None,
        typer.Option("--fixtures", help="path to calibration fixture dir"),
    ] = None,
    only: Annotated[
        str | None, typer.Option("--only", help="run only fixtures whose id contains this substring")
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="print model reasoning")] = False,
) -> None:
    """Run the current scoring prompt against calibration fixtures and report drift.

    Use this whenever you touch prompts/scoring.md, or when you suspect the
    model has changed behavior. Add fixtures by dropping YAML files into
    fixtures/calibration/ — see that dir's README.md.
    """
    c = cfg.load()
    fdir = fixtures_dir or (c.project_root / "fixtures" / "calibration")
    if not fdir.is_dir():
        typer.echo(f"no fixtures dir at {fdir}", err=True)
        raise typer.Exit(2)

    fixtures = cal.load_fixtures(fdir)
    if only:
        fixtures = [f for f in fixtures if only in f.id]
    if not fixtures:
        typer.echo("no fixtures matched", err=True)
        raise typer.Exit(2)

    prompt = sc.load_prompt(c.scoring_prompt_path, model_override=os.environ.get("SCOUT_LLM_MODEL"))
    client = _llm_client(c)

    typer.echo(f"running {len(fixtures)} fixtures against prompt {prompt.version} ({prompt.model})")
    typer.echo()
    typer.echo(f"{'':<2} {'id':<28} {'expected':>8} {'actual':>7} {'Δ':>6}  layer (got/exp)  notes")
    typer.echo("-" * 110)

    report = cal.run(fixtures, prompt=prompt, client=client)
    for d in report.diffs:
        mark = _VERDICT_MARK[d.verdict]
        layers = f"{d.actual.suggested_layer}/{d.fixture.expected.layer}"
        notes = "; ".join(d.failures) if d.failures else ""
        typer.echo(
            f"{mark:<2} {d.fixture.id:<28} {d.fixture.expected.final_score:>8.1f} "
            f"{d.actual.final_score:>7.1f} {d.score_delta:>+6.1f}  {layers:<16}  {notes}"
        )
        if verbose:
            typer.echo(f"     seed:    {d.actual.judgment_seed or '(empty)'}")
            typer.echo(f"     reason:  {d.actual.reasoning}")

    typer.echo()
    typer.echo(
        f"matches: {report.matches}/{report.total}   "
        f"mean |Δ|: {report.mean_abs_delta:.2f}   "
        f"max |Δ|: {report.max_abs_delta:.2f}"
    )
    raise typer.Exit(0 if report.matches == report.total else 1)


@app.command()
def doctor() -> None:
    """Self-check: paths, keys, db connectivity."""
    c = cfg.load()
    ok = True

    def check(label: str, cond: bool, hint: str = "") -> None:
        nonlocal ok
        mark = "OK" if cond else "FAIL"
        typer.echo(f"[{mark}] {label}{('  -> ' + hint) if not cond and hint else ''}")
        ok = ok and cond

    check("project root", c.project_root.exists())
    check("scoring prompt", c.scoring_prompt_path.exists(), str(c.scoring_prompt_path))
    check("keywords config", c.keywords_path.exists(), str(c.keywords_path))
    check("ANTHROPIC_API_KEY", bool(c.anthropic_api_key), "export it in your shell")
    try:
        db.connect(c.db_path).close()
        check("sqlite write", True)
    except Exception as e:
        check("sqlite write", False, str(e))
    sys.exit(0 if ok else 1)
