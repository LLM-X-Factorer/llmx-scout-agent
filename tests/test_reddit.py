import httpx
import pytest
import respx

from scout.sources.reddit import COMMENTS, LISTING, RedditSource


@pytest.fixture
def client():
    return httpx.Client(timeout=5)


def _listing(*posts: dict) -> dict:
    return {"data": {"children": [{"data": p} for p in posts]}}


def _post(**overrides) -> dict:
    base = {
        "id": "abc",
        "title": "Test post",
        "permalink": "/r/LocalLLaMA/comments/abc/test_post/",
        "url": "https://example.com/article",
        "is_self": False,
        "selftext": "",
        "ups": 100,
        "num_comments": 5,
        "created_utc": 1700000000.0,
        "author": "alice",
    }
    base.update(overrides)
    return base


@respx.mock
def test_discover_link_post(client):
    respx.get(LISTING.format(subreddit="LocalLLaMA")).respond(
        200, json=_listing(_post(id="p1", title="Cool article", url="https://blog.example.com/x"))
    )
    src = RedditSource(client=client, subreddits=("LocalLLaMA",), throttle_s=0)
    out = src.discover(limit=5)
    assert len(out) == 1
    cand = out[0]
    assert cand.source_platform == "reddit"
    assert cand.external_id == "p1"
    assert cand.original_url == "https://blog.example.com/x"
    assert cand.primary_url != cand.original_url  # link post: primary != original
    assert cand.metrics["reddit_upvotes"] == 100
    assert cand.metrics["reddit_comments"] == 5


@respx.mock
def test_discover_selfpost_keeps_primary_url_as_original(client):
    respx.get(LISTING.format(subreddit="LocalLLaMA")).respond(
        200, json=_listing(_post(id="p2", is_self=True, selftext="Body text", url="https://www.reddit.com/r/LocalLLaMA/comments/p2/"))
    )
    src = RedditSource(client=client, subreddits=("LocalLLaMA",), throttle_s=0)
    cand = src.discover(limit=5)[0]
    assert cand.primary_url == cand.original_url
    assert cand.snippet == "Body text"


@respx.mock
def test_discover_skips_removed_and_nsfw(client):
    respx.get(LISTING.format(subreddit="r1")).respond(
        200,
        json=_listing(
            _post(id="ok", title="Fine"),
            _post(id="removed", title="Removed", removed_by_category="moderator"),
            _post(id="nsfw", title="NSFW", over_18=True),
        ),
    )
    src = RedditSource(client=client, subreddits=("r1",), throttle_s=0)
    ids = [c.external_id for c in src.discover(limit=10)]
    assert ids == ["ok"]


@respx.mock
def test_discover_dedupes_across_subreddits_by_url(client):
    same_url = "https://blog.example.com/shared"
    respx.get(LISTING.format(subreddit="r1")).respond(
        200, json=_listing(_post(id="x1", url=same_url))
    )
    respx.get(LISTING.format(subreddit="r2")).respond(
        200, json=_listing(_post(id="x2", url=same_url))
    )
    src = RedditSource(client=client, subreddits=("r1", "r2"), throttle_s=0)
    out = src.discover(limit=10)
    assert len(out) == 1, "same external URL across subs should dedupe"


@respx.mock
def test_discover_truncates_long_selftext(client):
    long_body = "x" * 2000
    respx.get(LISTING.format(subreddit="r1")).respond(
        200, json=_listing(_post(id="p", is_self=True, selftext=long_body))
    )
    src = RedditSource(client=client, subreddits=("r1",), throttle_s=0)
    cand = src.discover(limit=1)[0]
    assert cand.snippet is not None
    assert len(cand.snippet) <= 1100  # 1000 + ellipsis margin
    assert cand.snippet.endswith("...")


@respx.mock
def test_fetch_top_comments_skips_more_kind_and_removed(client):
    respx.get(COMMENTS.format(post_id="p1")).respond(
        200,
        json=[
            {"data": {"children": []}},  # post listing
            {
                "data": {
                    "children": [
                        {"kind": "t1", "data": {"author": "alice", "body": "real comment", "score": 5}},
                        {"kind": "more", "data": {}},
                        {"kind": "t1", "data": {"author": "bob", "body": "[removed]", "score": 1}},
                        {"kind": "t1", "data": {"author": "carol", "body": "another real one", "score": 3}},
                    ]
                }
            },
        ],
    )
    src = RedditSource(client=client, subreddits=(), throttle_s=0)
    out = src.fetch_top_comments("p1", limit=5)
    assert [c["author"] for c in out] == ["alice", "carol"]
