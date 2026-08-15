from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def parse_range(*, range_key: str, tz_name: str) -> tuple[str, str, str, str]:
    today = datetime.now(ZoneInfo(tz_name)).date()
    mapping = {"7d": 7, "30d": 30, "90d": 90}
    days = mapping.get(range_key, 7)
    if range_key == "all":
        return "1970-01-01", today.isoformat(), "1970-01-01", "1970-01-01"
    current_start = today - timedelta(days=days - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    return current_start.isoformat(), today.isoformat(), previous_start.isoformat(), previous_end.isoformat()


def metric_sum(*, connection: sqlite3.Connection, metric: str, start: str, end: str) -> float:
    row = connection.execute(
        """
        SELECT COALESCE(SUM(value), 0) AS total
        FROM daily_metrics
        WHERE metric = ? AND local_date >= ? AND local_date <= ?
        """,
        (metric, start, end),
    ).fetchone()
    return float(row["total"])


def metric_avg(*, connection: sqlite3.Connection, metric: str, start: str, end: str) -> float | None:
    row = connection.execute(
        """
        SELECT AVG(value) AS avg_value
        FROM daily_metrics
        WHERE metric = ? AND local_date >= ? AND local_date <= ?
        """,
        (metric, start, end),
    ).fetchone()
    if row["avg_value"] is None:
        return None
    return float(row["avg_value"])


def instant_avg(*, connection: sqlite3.Connection, metric: str, start: str, end: str) -> float | None:
    row = connection.execute(
        """
        SELECT AVG(value) AS avg_value
        FROM instant_metrics
        WHERE metric = ? AND local_date >= ? AND local_date <= ?
        """,
        (metric, start, end),
    ).fetchone()
    if row["avg_value"] is None:
        return None
    return float(row["avg_value"])


def sleep_hours(*, connection: sqlite3.Connection, start: str, end: str) -> float:
    row = connection.execute(
        """
        SELECT COALESCE(SUM(duration_sec), 0) AS total
        FROM sleep_sessions
        WHERE local_date >= ? AND local_date <= ?
        """,
        (start, end),
    ).fetchone()
    return float(row["total"]) / 3600


def workout_minutes(*, connection: sqlite3.Connection, start: str, end: str) -> float:
    row = connection.execute(
        """
        SELECT COALESCE(SUM(duration_sec), 0) AS total
        FROM workouts
        WHERE local_date >= ? AND local_date <= ?
        """,
        (start, end),
    ).fetchone()
    return float(row["total"]) / 60


def wow_pct(*, current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100


def series(*, connection: sqlite3.Connection, metric: str, start: str, end: str, granularity: str) -> list[dict]:
    if metric == "sleep_hours":
        sql = """
            SELECT local_date AS bucket, SUM(duration_sec) / 3600.0 AS value
            FROM sleep_sessions
            WHERE local_date >= ? AND local_date <= ?
            GROUP BY local_date
            ORDER BY local_date
        """
        rows = connection.execute(sql, (start, end)).fetchall()
    elif metric in {"weight_kg", "rhr_bpm"}:
        sql = """
            SELECT local_date AS bucket, AVG(value) AS value
            FROM instant_metrics
            WHERE metric = ? AND local_date >= ? AND local_date <= ?
            GROUP BY local_date
            ORDER BY local_date
        """
        rows = connection.execute(sql, (metric, start, end)).fetchall()
    else:
        sql = """
            SELECT local_date AS bucket, value
            FROM daily_metrics
            WHERE metric = ? AND local_date >= ? AND local_date <= ?
            ORDER BY local_date
        """
        rows = connection.execute(sql, (metric, start, end)).fetchall()

    points = [{"date": row["bucket"], "value": float(row["value"])} for row in rows]
    if granularity != "week":
        return points

    weekly: dict[str, list[float]] = {}
    for point in points:
        parsed = date.fromisoformat(point["date"])
        week_start = (parsed - timedelta(days=parsed.weekday())).isoformat()
        weekly.setdefault(week_start, []).append(point["value"])
    return [{"date": week, "value": sum(values)} for week, values in weekly.items()]
