"""Thin SQLite wrapper. Three tables, no ORM."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Literal

Decision = Literal["packed", "low_score", "filtered_out", "failed", "resurge_packed"]

_SCHEMA = Path(__file__).parent / "schema.sql"


# Python 3.12 deprecated the implicit datetime <-> TIMESTAMP adapters.
# Register explicit ISO-8601 ones so callers can keep passing datetimes.
def _adapt_datetime(dt: datetime) -> str:
    return dt.isoformat()


def _convert_timestamp(raw: bytes) -> datetime:
    return datetime.fromisoformat(raw.decode())


sqlite3.register_adapter(datetime, _adapt_datetime)
sqlite3.register_converter("TIMESTAMP", _convert_timestamp)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA.read_text())
    return conn


# ---- dedup ----


def upsert_dedup(
    conn: sqlite3.Connection,
    *,
    url_hash: str,
    canonical_url: str,
    seen_at: datetime,
    metrics: dict[str, int | None] | None = None,
) -> None:
    payload = json.dumps(metrics) if metrics else None
    conn.execute(
        """
        INSERT INTO dedup (url_hash, canonical_url, first_seen_at, last_seen_at,
                           seen_count, last_metrics_json, decision)
        VALUES (?, ?, ?, ?, 1, ?, 'low_score')
        ON CONFLICT(url_hash) DO UPDATE SET
            last_seen_at = excluded.last_seen_at,
            seen_count = dedup.seen_count + 1,
            last_metrics_json = COALESCE(excluded.last_metrics_json, dedup.last_metrics_json)
        """,
        (url_hash, canonical_url, seen_at, seen_at, payload),
    )
    conn.commit()


def record_decision(
    conn: sqlite3.Connection,
    *,
    url_hash: str,
    decision: Decision,
    pack_id: str | None = None,
    last_score: float | None = None,
) -> None:
    conn.execute(
        """
        UPDATE dedup
           SET decision = ?, pack_id = COALESCE(?, pack_id), last_score = COALESCE(?, last_score)
         WHERE url_hash = ?
        """,
        (decision, pack_id, last_score, url_hash),
    )
    conn.commit()


def get_dedup(conn: sqlite3.Connection, url_hash: str) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM dedup WHERE url_hash = ?", (url_hash,))
    return cur.fetchone()


# ---- score history ----


def append_score(
    conn: sqlite3.Connection,
    *,
    url_hash: str,
    scored_at: datetime,
    prompt_version: str,
    score: float,
    payload: dict,
) -> None:
    conn.execute(
        """
        INSERT INTO score_history (url_hash, scored_at, prompt_version, score, payload_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (url_hash, scored_at, prompt_version, score, json.dumps(payload, ensure_ascii=False)),
    )
    conn.commit()


# ---- source health ----


def mark_source_ok(conn: sqlite3.Connection, source: str, at: datetime) -> None:
    conn.execute(
        """
        INSERT INTO source_health (source, last_ok_at, fail_streak)
        VALUES (?, ?, 0)
        ON CONFLICT(source) DO UPDATE SET last_ok_at = excluded.last_ok_at, fail_streak = 0
        """,
        (source, at),
    )
    conn.commit()


def mark_source_fail(conn: sqlite3.Connection, source: str, at: datetime) -> int:
    conn.execute(
        """
        INSERT INTO source_health (source, last_fail_at, fail_streak)
        VALUES (?, ?, 1)
        ON CONFLICT(source) DO UPDATE SET
            last_fail_at = excluded.last_fail_at,
            fail_streak = source_health.fail_streak + 1
        """,
        (source, at),
    )
    conn.commit()
    cur = conn.execute("SELECT fail_streak FROM source_health WHERE source = ?", (source,))
    row = cur.fetchone()
    return int(row["fail_streak"]) if row else 0
