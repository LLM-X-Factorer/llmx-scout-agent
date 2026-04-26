import httpx
import pytest
import respx

from scout.sources.hacker_news import API, HackerNewsSource


@pytest.fixture
def client():
    return httpx.Client(base_url="https://x", timeout=5)


@respx.mock
def test_discover_filters_non_stories(client):
    respx.get(f"{API}/topstories.json").respond(json=[1, 2, 3])
    respx.get(f"{API}/item/1.json").respond(
        json={
            "id": 1,
            "type": "story",
            "title": "Story",
            "url": "https://e.com/a",
            "score": 5,
            "time": 1700000000,
        }
    )
    respx.get(f"{API}/item/2.json").respond(json={"id": 2, "type": "comment", "text": "..."})
    respx.get(f"{API}/item/3.json").respond(
        json={
            "id": 3,
            "type": "story",
            "title": "Dead",
            "score": 1,
            "time": 1700000000,
            "dead": True,
        }
    )

    src = HackerNewsSource(client=client, throttle_s=0)
    out = src.discover(limit=3)
    assert len(out) == 1
    assert out[0].external_id == "1"
    assert out[0].metrics["hn_score"] == 5
    assert out[0].title == "Story"
    assert out[0].source_platform == "hacker_news"
    assert "news.ycombinator.com/item?id=1" in out[0].primary_url


@respx.mock
def test_discover_uses_hn_url_when_story_lacks_external_url(client):
    respx.get(f"{API}/topstories.json").respond(json=[10])
    respx.get(f"{API}/item/10.json").respond(
        json={"id": 10, "type": "story", "title": "Ask HN: foo", "score": 9, "time": 1700000000}
    )
    src = HackerNewsSource(client=client, throttle_s=0)
    out = src.discover(limit=1)
    assert "news.ycombinator.com/item?id=10" in out[0].original_url


@respx.mock
def test_fetch_top_comments_skips_dead(client):
    item = {"id": 100, "kids": [201, 202, 203]}
    respx.get(f"{API}/item/201.json").respond(json={"id": 201, "by": "alice", "text": "hi"})
    respx.get(f"{API}/item/202.json").respond(json={"id": 202, "dead": True})
    respx.get(f"{API}/item/203.json").respond(json={"id": 203, "by": "bob", "text": "hello"})
    src = HackerNewsSource(client=client, throttle_s=0)
    out = src.fetch_top_comments(item, limit=2)
    assert [c["by"] for c in out] == ["alice", "bob"]
