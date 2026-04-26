"""LLM-based scoring stage.

Loads `prompts/scoring.md`, builds a request, calls Anthropic, parses JSON.
The LLM client is injected so tests can plug a fake without hitting the API.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import yaml

from scout.models import Candidate, ControversySignal, ScoreResult


@dataclass(frozen=True)
class PromptBundle:
    version: str
    model: str
    temperature: float
    max_tokens: int
    system: str
    user_template: str


class LLMClient(Protocol):
    def complete(
        self, *, model: str, system: str, user: str, temperature: float, max_tokens: int
    ) -> str: ...


# ---- prompt loader ----

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
_USER_RE = re.compile(r"##\s*USER[^\n]*\n(.*?)(?=\n## |\Z)", re.DOTALL | re.IGNORECASE)
_SYSTEM_RE = re.compile(r"##\s*SYSTEM[^\n]*\n(.*?)(?=\n## |\Z)", re.DOTALL | re.IGNORECASE)


def load_prompt(path: Path, *, model_override: str | None = None) -> PromptBundle:
    raw = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        raise ValueError(f"prompt file {path} has no YAML frontmatter")
    meta = yaml.safe_load(m.group(1))
    body = m.group(2)
    sys_m = _SYSTEM_RE.search(body)
    usr_m = _USER_RE.search(body)
    if not sys_m or not usr_m:
        raise ValueError(f"prompt file {path} is missing ## SYSTEM or ## USER section")
    return PromptBundle(
        version=str(meta["version"]),
        model=model_override or str(meta.get("model", "claude-sonnet-4-6")),
        temperature=float(meta.get("temperature", 0.2)),
        max_tokens=int(meta.get("max_tokens", 1200)),
        system=sys_m.group(1).strip(),
        user_template=usr_m.group(1).strip(),
    )


# ---- input rendering ----


def _format_metrics(metrics: dict[str, int | None]) -> str:
    bits = [f"{k}={v}" for k, v in metrics.items() if v is not None]
    return ", ".join(bits) if bits else "(none)"


def render_user(template: str, candidate: Candidate, *, comments_preview: str = "") -> str:
    repl = {
        "platform": candidate.source_platform,
        "title": candidate.title,
        "primary_url": candidate.primary_url,
        "original_url": candidate.original_url,
        "author": candidate.author or "(unknown)",
        "published_at": candidate.published_at.isoformat()
        if candidate.published_at
        else "(unknown)",
        "metrics_summary": _format_metrics(candidate.metrics),
        "matched_keywords": ", ".join(candidate.matched_keywords) or "(none)",
        "snippet": candidate.snippet or "(no snippet)",
        "comments_preview": comments_preview or "(no comments fetched)",
    }
    out = template
    for k, v in repl.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


# ---- response parsing ----

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_response(raw: str, *, prompt_version: str) -> ScoreResult:
    """Tolerate small formatting noise: pull the first {...} block and parse."""
    m = _JSON_BLOCK_RE.search(raw)
    if not m:
        raise ValueError(f"no JSON object found in LLM response: {raw[:200]!r}")
    data = json.loads(m.group(0))
    scores = data["scores"]
    signals = [ControversySignal(**s) for s in data.get("controversy_signals", [])]
    return ScoreResult(
        judgment_space=float(scores["judgment_space"]),
        controversy=float(scores["controversy"]),
        info_density=float(scores["info_density"]),
        final_score=float(scores["final_score"]),
        judgment_seed=str(data.get("judgment_seed") or ""),
        suggested_layer=data.get("suggested_layer") or "unsure",
        controversy_signals=signals,
        reasoning=str(data.get("reasoning") or ""),
        prompt_version=prompt_version,
    )


# ---- the public entry point ----


def score(
    candidate: Candidate,
    *,
    prompt: PromptBundle,
    client: LLMClient,
    comments_preview: str = "",
) -> ScoreResult:
    user = render_user(prompt.user_template, candidate, comments_preview=comments_preview)
    raw = client.complete(
        model=prompt.model,
        system=prompt.system,
        user=user,
        temperature=prompt.temperature,
        max_tokens=prompt.max_tokens,
    )
    return parse_response(raw, prompt_version=prompt.version)


# ---- production client (Anthropic) ----


class AnthropicClient:
    def __init__(self, api_key: str) -> None:
        # Imported lazily so tests don't need the package wired up.
        from anthropic import Anthropic

        self._sdk = Anthropic(api_key=api_key)

    def complete(
        self, *, model: str, system: str, user: str, temperature: float, max_tokens: int
    ) -> str:
        msg = self._sdk.messages.create(
            model=model,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # The SDK returns a list of content blocks; we only ever ask for text.
        chunks = [getattr(b, "text", "") for b in msg.content]
        return "".join(chunks)


# ---- dev/test client (OpenRouter, OpenAI-compatible) ----
#
# This exists so we can exercise the pipeline without an Anthropic key.
# Production stays on Anthropic; see CLAUDE.md decision log.


class OpenRouterClient:
    """OpenAI-compatible chat completions against openrouter.ai."""

    BASE = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str, *, timeout: float = 60.0) -> None:
        import httpx

        self._client = httpx.Client(
            base_url=self.BASE,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                # OpenRouter recommends these for attribution / abuse handling.
                "HTTP-Referer": "https://github.com/LLM-X-Factorer/llmx-scout-agent",
                "X-Title": "llmx-scout-agent",
            },
        )

    def complete(
        self, *, model: str, system: str, user: str, temperature: float, max_tokens: int
    ) -> str:
        r = self._client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        r.raise_for_status()
        body = r.json()
        # OpenAI-compatible: choices[0].message.content
        return body["choices"][0]["message"]["content"] or ""
