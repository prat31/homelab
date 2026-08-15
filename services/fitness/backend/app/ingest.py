from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from app.config import Settings
from app.db import connect_warehouse
from app.drive import content_hash_for_drive_file, download_file, is_drive_configured, list_export_files, sha256_file
from app.mappings import CALORIES_TO_KCAL, EXERCISE_TYPES, GRAMS_TO_KG, METERS_TO_KM, SLEEP_STAGES


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def blob_uuid(value: bytes | None) -> str:
    if not value:
        return ""
    try:
        return str(UUID(bytes=value))
    except ValueError:
        return value.hex()


def millis_to_utc(value: int | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def epoch_day_to_date(value: int | None, *, tz_name: str) -> str | None:
    if value is None:
        return None
    return (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(days=int(value))).date().isoformat()


def package_rank(*, package: str | None, priority: list[str]) -> int:
    if not package:
        return 10_000
    if package in priority:
        return priority.index(package)
    return 1_000 + hash(package) % 100


def pick_source_rows(*, rows: list[sqlite3.Row], priority: list[str]) -> list[sqlite3.Row]:
    grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        grouped[row["package_name"] or ""].append(row)
    if not grouped:
        return []
    best_package = min(grouped.keys(), key=lambda name: package_rank(package=name, priority=priority))
    return grouped[best_package]


def overlapping(*, start_a: int, end_a: int, start_b: int, end_b: int, slop_ms: int = 5 * 60 * 1000) -> bool:
    return start_a <= end_b + slop_ms and start_b <= end_a + slop_ms


def open_export(*, path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def already_ingested(*, warehouse: sqlite3.Connection, content_hash: str) -> bool:
    row = warehouse.execute(
        "SELECT id FROM ingested_exports WHERE content_hash = ? AND status = 'ok'",
        (content_hash,),
    ).fetchone()
    return row is not None


def record_ingest(
    *,
    warehouse: sqlite3.Connection,
    content_hash: str,
    filename: str,
    status: str,
    drive_file_id: str | None = None,
    size_bytes: int | None = None,
    modified_time: str | None = None,
    error: str | None = None,
) -> None:
    warehouse.execute(
        """
        INSERT INTO ingested_exports (
            drive_file_id, filename, content_hash, size_bytes, modified_time, ingested_at, status, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(content_hash) DO UPDATE SET
            ingested_at = excluded.ingested_at,
            status = excluded.status,
            error = excluded.error,
            filename = excluded.filename
        """,
        (drive_file_id, filename, content_hash, size_bytes, modified_time, utc_now(), status, error),
    )
    warehouse.commit()


def rebuild_from_export(*, settings: Settings, export_path: Path) -> dict[str, int]:
    warehouse = connect_warehouse(db_path=settings.warehouse_path)
    export = open_export(path=export_path)
    try:
        warehouse.execute("DELETE FROM daily_metrics")
        warehouse.execute("DELETE FROM workouts")
        warehouse.execute("DELETE FROM sleep_sessions")
        warehouse.execute("DELETE FROM instant_metrics")
        counts = {
            "daily": load_daily_metrics(export=export, warehouse=warehouse, settings=settings),
            "workouts": load_workouts(export=export, warehouse=warehouse, settings=settings),
            "sleep": load_sleep(export=export, warehouse=warehouse, settings=settings),
            "instant": load_instant_metrics(export=export, warehouse=warehouse, settings=settings),
        }
        warehouse.commit()
        return counts
    finally:
        export.close()
        warehouse.close()


def load_daily_metrics(*, export: sqlite3.Connection, warehouse: sqlite3.Connection, settings: Settings) -> int:
    specs = [
        (
            "steps",
            """
            SELECT s.local_date, a.package_name, SUM(s.count) AS value
            FROM steps_record_table s
            LEFT JOIN application_info_table a ON a.row_id = s.app_info_id
            WHERE s.local_date IS NOT NULL
            GROUP BY s.local_date, a.package_name
            """,
            1.0,
        ),
        (
            "distance_km",
            """
            SELECT d.local_date, a.package_name, SUM(d.distance) AS value
            FROM distance_record_table d
            LEFT JOIN application_info_table a ON a.row_id = d.app_info_id
            WHERE d.local_date IS NOT NULL
            GROUP BY d.local_date, a.package_name
            """,
            METERS_TO_KM,
        ),
        (
            "calories_kcal",
            """
            SELECT c.local_date, a.package_name, SUM(c.energy) AS value
            FROM total_calories_burned_record_table c
            LEFT JOIN application_info_table a ON a.row_id = c.app_info_id
            WHERE c.local_date IS NOT NULL
            GROUP BY c.local_date, a.package_name
            """,
            CALORIES_TO_KCAL,
        ),
        (
            "active_calories_kcal",
            """
            SELECT c.local_date, a.package_name, SUM(c.energy) AS value
            FROM active_calories_burned_record_table c
            LEFT JOIN application_info_table a ON a.row_id = c.app_info_id
            WHERE c.local_date IS NOT NULL
            GROUP BY c.local_date, a.package_name
            """,
            CALORIES_TO_KCAL,
        ),
        (
            "elevation_m",
            """
            SELECT e.local_date, a.package_name, SUM(e.elevation) AS value
            FROM elevation_gained_record_table e
            LEFT JOIN application_info_table a ON a.row_id = e.app_info_id
            WHERE e.local_date IS NOT NULL
            GROUP BY e.local_date, a.package_name
            """,
            1.0,
        ),
    ]
    written = 0
    for metric, sql, divisor in specs:
        by_day: dict[int, list[sqlite3.Row]] = defaultdict(list)
        for row in export.execute(sql):
            by_day[row["local_date"]].append(row)
        for local_date, rows in by_day.items():
            chosen = pick_source_rows(rows=rows, priority=settings.priority_packages)
            if not chosen:
                continue
            value = sum(float(item["value"] or 0) for item in chosen) / divisor
            warehouse.execute(
                "INSERT INTO daily_metrics (local_date, metric, value, source_package) VALUES (?, ?, ?, ?)",
                (epoch_day_to_date(local_date, tz_name=settings.fitness_tz), metric, value, chosen[0]["package_name"]),
            )
            written += 1
    return written


def load_workouts(*, export: sqlite3.Connection, warehouse: sqlite3.Connection, settings: Settings) -> int:
    sessions = list(
        export.execute(
            """
            SELECT e.row_id, e.uuid, e.start_time, e.end_time, e.local_date, e.exercise_type,
                   a.package_name
            FROM exercise_session_record_table e
            LEFT JOIN application_info_table a ON a.row_id = e.app_info_id
            WHERE e.start_time IS NOT NULL AND e.end_time IS NOT NULL
            ORDER BY e.start_time
            """
        )
    )
    kept: list[sqlite3.Row] = []
    for session in sessions:
        duplicate = False
        for existing in kept:
            if overlapping(
                start_a=session["start_time"],
                end_a=session["end_time"],
                start_b=existing["start_time"],
                end_b=existing["end_time"],
            ):
                current_rank = package_rank(package=session["package_name"], priority=settings.priority_packages)
                existing_rank = package_rank(package=existing["package_name"], priority=settings.priority_packages)
                if current_rank < existing_rank:
                    kept.remove(existing)
                    kept.append(session)
                duplicate = True
                break
        if not duplicate:
            kept.append(session)

    hr_rows = list(
        export.execute("SELECT epoch_millis, beats_per_minute FROM heart_rate_record_series_table")
    )
    written = 0
    for session in kept:
        start = session["start_time"]
        end = session["end_time"]
        samples = [row["beats_per_minute"] for row in hr_rows if start <= row["epoch_millis"] <= end]
        avg_hr = sum(samples) / len(samples) if samples else None
        max_hr = max(samples) if samples else None
        exercise_type = session["exercise_type"]
        warehouse.execute(
            """
            INSERT OR REPLACE INTO workouts (
                uuid, start_utc, end_utc, local_date, exercise_type, exercise_name,
                duration_sec, source_package, avg_hr, max_hr
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                blob_uuid(session["uuid"]) or str(session["row_id"]),
                millis_to_utc(start),
                millis_to_utc(end),
                epoch_day_to_date(session["local_date"], tz_name=settings.fitness_tz),
                exercise_type,
                EXERCISE_TYPES.get(exercise_type, f"Type {exercise_type}"),
                int((end - start) / 1000),
                session["package_name"],
                avg_hr,
                max_hr,
            ),
        )
        written += 1
    return written


def load_sleep(*, export: sqlite3.Connection, warehouse: sqlite3.Connection, settings: Settings) -> int:
    written = 0
    for session in export.execute(
        """
        SELECT s.row_id, s.uuid, s.start_time, s.end_time, s.local_date, a.package_name
        FROM sleep_session_record_table s
        LEFT JOIN application_info_table a ON a.row_id = s.app_info_id
        """
    ):
        stages: dict[str, int] = defaultdict(int)
        for stage in export.execute(
            """
            SELECT stage_type, stage_start_time, stage_end_time
            FROM sleep_stages_table
            WHERE parent_key = ?
            """,
            (session["row_id"],),
        ):
            name = SLEEP_STAGES.get(stage["stage_type"], "sleeping")
            stages[name] += int((stage["stage_end_time"] - stage["stage_start_time"]) / 1000)
        warehouse.execute(
            """
            INSERT OR REPLACE INTO sleep_sessions (
                uuid, start_utc, end_utc, local_date, duration_sec, source_package,
                awake_sec, light_sec, deep_sec, rem_sec
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                blob_uuid(session["uuid"]) or str(session["row_id"]),
                millis_to_utc(session["start_time"]),
                millis_to_utc(session["end_time"]),
                epoch_day_to_date(session["local_date"], tz_name=settings.fitness_tz),
                int((session["end_time"] - session["start_time"]) / 1000),
                session["package_name"],
                stages.get("awake", 0),
                stages.get("light", 0),
                stages.get("deep", 0),
                stages.get("rem", 0),
            ),
        )
        written += 1
    return written


def load_instant_metrics(*, export: sqlite3.Connection, warehouse: sqlite3.Connection, settings: Settings) -> int:
    specs = [
        ("weight_kg", "weight_record_table", "weight", GRAMS_TO_KG),
        ("rhr_bpm", "resting_heart_rate_record_table", "beats_per_minute", 1.0),
        ("height_m", "height_record_table", "height", 1.0),
        ("bmr_kcal", "basal_metabolic_rate_record_table", "basal_metabolic_rate", CALORIES_TO_KCAL),
    ]
    written = 0
    for metric, table, column, divisor in specs:
        tables = {row[0] for row in export.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if table not in tables:
            continue
        sql = f"""
            SELECT t.time, t.local_date, t.{column} AS value, a.package_name
            FROM {table} t
            LEFT JOIN application_info_table a ON a.row_id = t.app_info_id
            WHERE t.time IS NOT NULL
        """
        by_day: dict[int, list[sqlite3.Row]] = defaultdict(list)
        for row in export.execute(sql):
            by_day[row["local_date"]].append(row)
        for local_date, rows in by_day.items():
            chosen = pick_source_rows(rows=rows, priority=settings.priority_packages)
            for row in chosen:
                warehouse.execute(
                    """
                    INSERT OR REPLACE INTO instant_metrics (local_date, metric, time_utc, value, source_package)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        epoch_day_to_date(local_date, tz_name=settings.fitness_tz),
                        metric,
                        millis_to_utc(row["time"]),
                        float(row["value"] or 0) / divisor,
                        row["package_name"],
                    ),
                )
                written += 1
    return written


def ingest_local_file(
    *,
    settings: Settings,
    path: Path,
    drive_file: dict[str, Any] | None = None,
) -> dict[str, Any]:
    warehouse = connect_warehouse(db_path=settings.warehouse_path)
    content_hash = (
        content_hash_for_drive_file(drive_file=drive_file, local_path=path)
        if drive_file
        else f"sha256:{sha256_file(path=path)}"
    )
    if already_ingested(warehouse=warehouse, content_hash=content_hash):
        warehouse.close()
        return {"status": "skipped", "content_hash": content_hash, "filename": path.name}

    try:
        counts = rebuild_from_export(settings=settings, export_path=path)
        record_ingest(
            warehouse=warehouse,
            content_hash=content_hash,
            filename=path.name,
            status="ok",
            drive_file_id=(drive_file or {}).get("id"),
            size_bytes=path.stat().st_size,
            modified_time=(drive_file or {}).get("modifiedTime"),
        )
        warehouse.close()
        return {"status": "ok", "content_hash": content_hash, "filename": path.name, "counts": counts}
    except Exception as exc:
        record_ingest(
            warehouse=warehouse,
            content_hash=content_hash,
            filename=path.name,
            status="error",
            drive_file_id=(drive_file or {}).get("id"),
            size_bytes=path.stat().st_size if path.exists() else None,
            modified_time=(drive_file or {}).get("modifiedTime"),
            error=str(exc),
        )
        warehouse.close()
        raise


def poll_drive(*, settings: Settings) -> dict[str, Any]:
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    if not is_drive_configured(settings=settings):
        return {"status": "drive_not_configured"}

    files = list_export_files(settings=settings)
    if not files:
        return {"status": "no_files"}

    warehouse = connect_warehouse(db_path=settings.warehouse_path)
    newest_new = None
    for drive_file in files:
        md5 = drive_file.get("md5Checksum")
        content_hash = f"md5:{md5}" if md5 else None
        if content_hash and already_ingested(warehouse=warehouse, content_hash=content_hash):
            continue
        newest_new = drive_file
        break
    warehouse.close()

    if newest_new is None:
        return {"status": "up_to_date", "seen": len(files)}

    dest = settings.exports_dir / newest_new["name"]
    download_file(settings=settings, file_id=newest_new["id"], dest_path=dest)
    result = ingest_local_file(settings=settings, path=dest, drive_file=newest_new)
    result["drive_file_id"] = newest_new["id"]
    return result


def ingest_exports_dir(*, settings: Settings) -> dict[str, Any]:
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    candidates = sorted(
        [path for path in settings.exports_dir.iterdir() if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return {"status": "no_local_exports"}
    return ingest_local_file(settings=settings, path=candidates[0])
