-- SQLite schema for scout dedup, source health, and score history.

CREATE TABLE IF NOT EXISTS dedup (
    url_hash          TEXT PRIMARY KEY,
    canonical_url     TEXT NOT NULL,
    first_seen_at     TIMESTAMP NOT NULL,
    last_seen_at      TIMESTAMP NOT NULL,
    seen_count        INTEGER NOT NULL DEFAULT 1,
    pack_id           TEXT,
    last_score        REAL,
    last_metrics_json TEXT,
    decision          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dedup_decision_seen
    ON dedup (decision, last_seen_at);

CREATE TABLE IF NOT EXISTS source_health (
    source       TEXT PRIMARY KEY,
    last_ok_at   TIMESTAMP,
    last_fail_at TIMESTAMP,
    fail_streak  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS score_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash       TEXT NOT NULL,
    scored_at      TIMESTAMP NOT NULL,
    prompt_version TEXT NOT NULL,
    score          REAL NOT NULL,
    payload_json   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_score_history_url
    ON score_history (url_hash, scored_at);
