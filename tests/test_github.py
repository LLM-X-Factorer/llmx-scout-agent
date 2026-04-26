from pathlib import Path

import httpx
import pytest
import respx

from scout.sources.github import TRENDING_URL, GitHubTrendingSource, _to_int

FIXTURE = Path(__file__).parent / "fixtures" / "github_trending.html"


@pytest.fixture
def client():
    return httpx.Client(timeout=5)


def test_to_int_handles_thousands_separator():
    assert _to_int("12,345") == 12345
    assert _to_int("1,139 stars today") == 1139
    assert _to_int("8") == 8
    assert _to_int(None) is None
    assert _to_int("(none)") is None


@respx.mock
def test_discover_parses_real_html_fixture(client):
    respx.get(TRENDING_URL).respond(200, text=FIXTURE.read_text())
    src = GitHubTrendingSource(client=client)
    out = src.discover(limit=10)

    assert len(out) == 3, "fixture has 3 articles"
    for cand in out:
        assert cand.source_platform == "github"
        # external_id is owner/repo
        assert "/" in cand.external_id
        assert cand.external_id.count("/") == 1
        assert cand.primary_url.startswith("https://github.com/")
        assert cand.author == cand.external_id.split("/")[0]
        # at least the total stars metric should parse
        assert cand.metrics["github_stars"] is not None
        assert cand.metrics["github_stars"] > 0


@respx.mock
def test_discover_respects_limit(client):
    respx.get(TRENDING_URL).respond(200, text=FIXTURE.read_text())
    src = GitHubTrendingSource(client=client)
    assert len(src.discover(limit=2)) == 2
    assert len(src.discover(limit=1)) == 1


@respx.mock
def test_discover_empty_when_html_structure_changes(client):
    """If GitHub renames the article CSS class, parser fails open (returns [])."""
    respx.get(TRENDING_URL).respond(200, text="<html><body><p>nothing here</p></body></html>")
    src = GitHubTrendingSource(client=client)
    assert src.discover(limit=10) == []


@respx.mock
def test_discover_skips_malformed_articles(client):
    """Article without h2/a is skipped, not crashed on."""
    html = """
    <html><body>
      <article class="Box-row">no link here</article>
      <article class="Box-row">
        <h2><a href="/foo/bar">foo/bar</a></h2>
        <a href="/foo/bar/stargazers">42</a>
      </article>
    </body></html>
    """
    respx.get(TRENDING_URL).respond(200, text=html)
    src = GitHubTrendingSource(client=client)
    out = src.discover(limit=10)
    assert len(out) == 1
    assert out[0].external_id == "foo/bar"
    assert out[0].metrics["github_stars"] == 42


@respx.mock
def test_discover_handles_missing_description(client):
    html = """
    <html><body>
      <article class="Box-row">
        <h2><a href="/owner/repo">owner / repo</a></h2>
        <a href="/owner/repo/stargazers">10</a>
      </article>
    </body></html>
    """
    respx.get(TRENDING_URL).respond(200, text=html)
    src = GitHubTrendingSource(client=client)
    cand = src.discover(limit=10)[0]
    assert cand.snippet is None
    # title falls back to owner/repo when no description
    assert cand.title == "owner/repo"


@respx.mock
def test_discover_propagates_http_error(client):
    respx.get(TRENDING_URL).respond(503)
    src = GitHubTrendingSource(client=client)
    with pytest.raises(httpx.HTTPStatusError):
        src.discover(limit=10)
