from pathlib import Path

import pytest

from scout.filter.scoring import load_prompt, parse_response, render_user, score
from scout.models import Candidate

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "scoring.md"


def _candidate() -> Candidate:
    return Candidate(
        source_platform="hacker_news",
        external_id="1",
        primary_url="https://news.ycombinator.com/item?id=1",
        original_url="https://example.com/x",
        url_hash="hash",
        title="Why we replaced LangChain with raw prompts",
        snippet="After 18 months in production...",
        metrics={"hn_score": 612, "hn_comments": 287},
        matched_keywords=["LangChain"],
    )


def test_prompt_loads_with_metadata():
    p = load_prompt(PROMPT_PATH)
    assert p.version == "v0.1"
    assert "判断空间" in p.system or "judgment_space" in p.system
    assert "{{title}}" in p.user_template
    assert "{{matched_keywords}}" in p.user_template


def test_render_user_replaces_all_placeholders():
    p = load_prompt(PROMPT_PATH)
    out = render_user(p.user_template, _candidate(), comments_preview="- @x: hi")
    assert "{{" not in out
    assert "LangChain" in out
    assert "612" in out


def test_parse_response_handles_pure_json():
    raw = (
        '{"scores":{"judgment_space":9,"controversy":8,"info_density":8,"final_score":8.4},'
        '"judgment_seed":"X but Y","suggested_layer":"留存层",'
        '"controversy_signals":[{"type":"expert_disagreement","evidence":"x"}],'
        '"reasoning":"ok"}'
    )
    r = parse_response(raw, prompt_version="v0.1")
    assert r.final_score == 8.4
    assert r.suggested_layer == "留存层"
    assert r.controversy_signals[0].type == "expert_disagreement"


def test_parse_response_handles_preamble_and_codefence():
    raw = """Here's my evaluation:
```json
{"scores":{"judgment_space":2,"controversy":1,"info_density":4,"final_score":2.0},
 "judgment_seed":"","suggested_layer":"unsure","controversy_signals":[],"reasoning":"low"}
```
"""
    r = parse_response(raw, prompt_version="v0.1")
    assert r.final_score == 2.0
    assert r.judgment_seed == ""


def test_parse_response_raises_on_garbage():
    with pytest.raises(ValueError):
        parse_response("nope no json here", prompt_version="v0.1")


class _FakeClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.last_user: str | None = None

    def complete(self, *, model, system, user, temperature, max_tokens):
        self.last_user = user
        return self.response


def test_score_uses_injected_client():
    p = load_prompt(PROMPT_PATH)
    fake = _FakeClient(
        '{"scores":{"judgment_space":7,"controversy":6,"info_density":7,"final_score":6.7},'
        '"judgment_seed":"X but Y","suggested_layer":"留存层","controversy_signals":[],'
        '"reasoning":"reasoning text"}'
    )
    r = score(_candidate(), prompt=p, client=fake, comments_preview="- @x: hi")
    assert r.final_score == 6.7
    assert r.prompt_version == "v0.1"
    assert "LangChain" in fake.last_user
