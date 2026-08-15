from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingested_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drive_file_id TEXT,
    filename TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    size_bytes INTEGER,
    modified_time TEXT,
    ingested_at TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS daily_metrics (
    local_date TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    source_package TEXT,
    PRIMARY KEY (local_date, metric)
);

CREATE TABLE IF NOT EXISTS workouts (
    uuid TEXT PRIMARY KEY,
    start_utc TEXT NOT NULL,
    end_utc TEXT NOT NULL,
    local_date TEXT NOT NULL,
    exercise_type INTEGER,
    exercise_name TEXT,
    duration_sec INTEGER NOT NULL,
    source_package TEXT,
    avg_hr REAL,
    max_hr REAL
);

CREATE TABLE IF NOT EXISTS sleep_sessions (
    uuid TEXT PRIMARY KEY,
    start_utc TEXT NOT NULL,
    end_utc TEXT NOT NULL,
    local_date TEXT NOT NULL,
    duration_sec INTEGER NOT NULL,
    source_package TEXT,
    awake_sec INTEGER DEFAULT 0,
    light_sec INTEGER DEFAULT 0,
    deep_sec INTEGER DEFAULT 0,
    rem_sec INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS instant_metrics (
    local_date TEXT NOT NULL,
    metric TEXT NOT NULL,
    time_utc TEXT NOT NULL,
    value REAL NOT NULL,
    source_package TEXT,
    PRIMARY KEY (local_date, metric, time_utc)
);
"""


def connect_warehouse(*, db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(SCHEMA)
    return connection
