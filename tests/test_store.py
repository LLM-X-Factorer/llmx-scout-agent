from datetime import UTC, datetime
from pathlib import Path

from scout.store import db


def test_dedup_lifecycle(tmp_path: Path):
    conn = db.connect(tmp_path / "scout.sqlite")
    now = datetime.now(UTC)
    db.upsert_dedup(
        conn, url_hash="h", canonical_url="https://x", seen_at=now, metrics={"hn_score": 100}
    )
    row = db.get_dedup(conn, "h")
    assert row is not None
    assert row["seen_count"] == 1
    assert row["decision"] == "low_score"

    # Repeated upsert increments seen_count
    db.upsert_dedup(
        conn, url_hash="h", canonical_url="https://x", seen_at=now, metrics={"hn_score": 200}
    )
    row = db.get_dedup(conn, "h")
    assert row["seen_count"] == 2

    db.record_decision(conn, url_hash="h", decision="packed", pack_id="pid", last_score=8.0)
    row = db.get_dedup(conn, "h")
    assert row["decision"] == "packed"
    assert row["pack_id"] == "pid"
    assert row["last_score"] == 8.0


def test_score_history_appends(tmp_path: Path):
    conn = db.connect(tmp_path / "scout.sqlite")
    now = datetime.now(UTC)
    db.append_score(
        conn,
        url_hash="h",
        scored_at=now,
        prompt_version="v0.1",
        score=7.5,
        payload={"k": "v"},
    )
    db.append_score(
        conn,
        url_hash="h",
        scored_at=now,
        prompt_version="v0.2",
        score=7.8,
        payload={"k": "v2"},
    )
    rows = list(conn.execute("SELECT * FROM score_history WHERE url_hash='h' ORDER BY id"))
    assert len(rows) == 2
    assert rows[0]["prompt_version"] == "v0.1"
    assert rows[1]["score"] == 7.8


def test_source_health_streak(tmp_path: Path):
    conn = db.connect(tmp_path / "scout.sqlite")
    now = datetime.now(UTC)
    s1 = db.mark_source_fail(conn, "hacker_news", now)
    s2 = db.mark_source_fail(conn, "hacker_news", now)
    assert (s1, s2) == (1, 2)
    db.mark_source_ok(conn, "hacker_news", now)
    cur = conn.execute("SELECT fail_streak FROM source_health WHERE source='hacker_news'")
    assert cur.fetchone()["fail_streak"] == 0
