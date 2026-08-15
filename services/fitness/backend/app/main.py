from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.db import connect_warehouse
from app.ingest import ingest_exports_dir, ingest_local_file, poll_drive
from app.queries import (
    instant_avg,
    metric_sum,
    parse_range,
    series,
    sleep_hours,
    workout_minutes,
    wow_pct,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fitness")
scheduler = AsyncIOScheduler()


def run_poll(settings: Settings) -> dict:
    drive_result = poll_drive(settings=settings)
    if drive_result.get("status") in {"drive_not_configured", "no_files"}:
        local_result = ingest_exports_dir(settings=settings)
        return {"drive": drive_result, "local": local_result}
    return {"drive": drive_result}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    connect_warehouse(db_path=settings.warehouse_path).close()
    scheduler.configure(timezone=ZoneInfo(settings.fitness_tz))
    scheduler.add_job(
        lambda: run_poll(settings),
        CronTrigger(hour=settings.drive_poll_hour, minute=0, timezone=settings.fitness_tz),
        id="drive-daily",
        replace_existing=True,
    )
    scheduler.start()
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, run_poll, settings)
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Fitness", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Header()] = None,
    api_key: Annotated[str | None, Query()] = None,
) -> None:
    if not settings.fitness_api_key:
        return
    provided = x_api_key or api_key
    if provided != settings.fitness_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


def warehouse(settings: Annotated[Settings, Depends(get_settings)]):
    connection = connect_warehouse(db_path=settings.warehouse_path)
    try:
        yield connection
    finally:
        connection.close()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/ingest", dependencies=[Depends(require_api_key)])
async def ingest_upload(
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
) -> dict:
    dest = settings.exports_dir / (file.filename or "upload.db")
    dest.write_bytes(await file.read())
    return ingest_local_file(settings=settings, path=dest)


@app.post("/api/ingest/drive", dependencies=[Depends(require_api_key)])
def ingest_drive(settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    return run_poll(settings)


@app.get("/api/ingest/status", dependencies=[Depends(require_api_key)])
def ingest_status(
    settings: Annotated[Settings, Depends(get_settings)],
    connection=Depends(warehouse),
) -> dict:
    latest = connection.execute(
        "SELECT filename, content_hash, ingested_at, status, error, drive_file_id FROM ingested_exports ORDER BY ingested_at DESC LIMIT 10"
    ).fetchall()
    counts = {
        "daily_metrics": connection.execute("SELECT COUNT(*) AS n FROM daily_metrics").fetchone()["n"],
        "workouts": connection.execute("SELECT COUNT(*) AS n FROM workouts").fetchone()["n"],
        "sleep_sessions": connection.execute("SELECT COUNT(*) AS n FROM sleep_sessions").fetchone()["n"],
    }
    return {
        "drive_configured": bool(settings.drive_folder_id),
        "tz": settings.fitness_tz,
        "counts": counts,
        "history": [dict(row) for row in latest],
    }


@app.get("/api/summary", dependencies=[Depends(require_api_key)])
def summary(
    settings: Annotated[Settings, Depends(get_settings)],
    range: str = "7d",
    connection=Depends(warehouse),
) -> dict:
    start, end, prev_start, prev_end = parse_range(range_key=range, tz_name=settings.fitness_tz)

    def pack(current: float, previous: float) -> dict:
        return {"current": current, "previous": previous, "wow_pct": wow_pct(current=current, previous=previous)}

    rhr_current = instant_avg(connection=connection, metric="rhr_bpm", start=start, end=end)
    rhr_previous = instant_avg(connection=connection, metric="rhr_bpm", start=prev_start, end=prev_end)
    return {
        "range": range,
        "start": start,
        "end": end,
        "steps": pack(
            metric_sum(connection=connection, metric="steps", start=start, end=end),
            metric_sum(connection=connection, metric="steps", start=prev_start, end=prev_end),
        ),
        "distance_km": pack(
            metric_sum(connection=connection, metric="distance_km", start=start, end=end),
            metric_sum(connection=connection, metric="distance_km", start=prev_start, end=prev_end),
        ),
        "calories_kcal": pack(
            metric_sum(connection=connection, metric="calories_kcal", start=start, end=end),
            metric_sum(connection=connection, metric="calories_kcal", start=prev_start, end=prev_end),
        ),
        "elevation_m": pack(
            metric_sum(connection=connection, metric="elevation_m", start=start, end=end),
            metric_sum(connection=connection, metric="elevation_m", start=prev_start, end=prev_end),
        ),
        "sleep_hours": pack(
            sleep_hours(connection=connection, start=start, end=end),
            sleep_hours(connection=connection, start=prev_start, end=prev_end),
        ),
        "workout_minutes": pack(
            workout_minutes(connection=connection, start=start, end=end),
            workout_minutes(connection=connection, start=prev_start, end=prev_end),
        ),
        "rhr_bpm": pack(rhr_current or 0, rhr_previous or 0),
    }


@app.get("/api/series/{metric}", dependencies=[Depends(require_api_key)])
def metric_series(
    metric: str,
    settings: Annotated[Settings, Depends(get_settings)],
    range: str = "30d",
    granularity: str = "day",
    connection=Depends(warehouse),
) -> dict:
    start, end, _, _ = parse_range(range_key=range, tz_name=settings.fitness_tz)
    return {
        "metric": metric,
        "points": series(connection=connection, metric=metric, start=start, end=end, granularity=granularity),
    }


@app.get("/api/workouts", dependencies=[Depends(require_api_key)])
def list_workouts(
    settings: Annotated[Settings, Depends(get_settings)],
    range: str = "30d",
    connection=Depends(warehouse),
) -> dict:
    start, end, _, _ = parse_range(range_key=range, tz_name=settings.fitness_tz)
    rows = connection.execute(
        """
        SELECT uuid, start_utc, end_utc, local_date, exercise_name, duration_sec,
               source_package, avg_hr, max_hr
        FROM workouts
        WHERE local_date >= ? AND local_date <= ?
        ORDER BY start_utc DESC
        """,
        (start, end),
    ).fetchall()
    return {"workouts": [dict(row) for row in rows]}


@app.get("/api/sleep", dependencies=[Depends(require_api_key)])
def list_sleep(
    settings: Annotated[Settings, Depends(get_settings)],
    range: str = "30d",
    connection=Depends(warehouse),
) -> dict:
    start, end, _, _ = parse_range(range_key=range, tz_name=settings.fitness_tz)
    rows = connection.execute(
        """
        SELECT uuid, start_utc, end_utc, local_date, duration_sec, source_package,
               awake_sec, light_sec, deep_sec, rem_sec
        FROM sleep_sessions
        WHERE local_date >= ? AND local_date <= ?
        ORDER BY start_utc DESC
        """,
        (start, end),
    ).fetchall()
    return {"nights": [dict(row) for row in rows]}


@app.get("/api/body", dependencies=[Depends(require_api_key)])
def list_body(
    settings: Annotated[Settings, Depends(get_settings)],
    range: str = "90d",
    connection=Depends(warehouse),
) -> dict:
    start, end, _, _ = parse_range(range_key=range, tz_name=settings.fitness_tz)
    rows = connection.execute(
        """
        SELECT local_date, metric, time_utc, value, source_package
        FROM instant_metrics
        WHERE local_date >= ? AND local_date <= ?
        ORDER BY time_utc
        """,
        (start, end),
    ).fetchall()
    return {"points": [dict(row) for row in rows]}


@app.get("/api/sources", dependencies=[Depends(require_api_key)])
def sources(connection=Depends(warehouse)) -> dict:
    rows = connection.execute(
        """
        SELECT metric, source_package, COUNT(*) AS days
        FROM daily_metrics
        GROUP BY metric, source_package
        ORDER BY metric, days DESC
        """
    ).fetchall()
    return {"sources": [dict(row) for row in rows]}


@app.get("/api/widgets/overview")
def widget_overview(
    settings: Annotated[Settings, Depends(get_settings)],
    connection=Depends(warehouse),
    x_api_key: Annotated[str | None, Header()] = None,
    api_key: Annotated[str | None, Query()] = None,
) -> dict:
    require_api_key(settings=settings, x_api_key=x_api_key, api_key=api_key)
    start, end, _, _ = parse_range(range_key="7d", tz_name=settings.fitness_tz)
    rhr = instant_avg(connection=connection, metric="rhr_bpm", start=start, end=end)
    return {
        "steps": round(metric_sum(connection=connection, metric="steps", start=start, end=end)),
        "distance_km": round(metric_sum(connection=connection, metric="distance_km", start=start, end=end), 1),
        "kcal": round(metric_sum(connection=connection, metric="calories_kcal", start=start, end=end)),
        "sleep_hours": round(sleep_hours(connection=connection, start=start, end=end), 1),
        "workout_minutes": round(workout_minutes(connection=connection, start=start, end=end)),
        "rhr": round(rhr) if rhr else None,
    }


@app.get("/api/widgets/week")
def widget_week(
    settings: Annotated[Settings, Depends(get_settings)],
    connection=Depends(warehouse),
    x_api_key: Annotated[str | None, Header()] = None,
    api_key: Annotated[str | None, Query()] = None,
) -> dict:
    require_api_key(settings=settings, x_api_key=x_api_key, api_key=api_key)
    start, end, prev_start, prev_end = parse_range(range_key="7d", tz_name=settings.fitness_tz)
    steps = metric_sum(connection=connection, metric="steps", start=start, end=end)
    steps_prev = metric_sum(connection=connection, metric="steps", start=prev_start, end=prev_end)
    km = metric_sum(connection=connection, metric="distance_km", start=start, end=end)
    km_prev = metric_sum(connection=connection, metric="distance_km", start=prev_start, end=prev_end)
    sleep = sleep_hours(connection=connection, start=start, end=end)
    sleep_prev = sleep_hours(connection=connection, start=prev_start, end=prev_end)
    return {
        "steps": round(steps),
        "steps_last": round(steps_prev),
        "steps_wow": f"{wow_pct(current=steps, previous=steps_prev):+.0f}%" if wow_pct(current=steps, previous=steps_prev) is not None else "n/a",
        "km": round(km, 1),
        "km_last": round(km_prev, 1),
        "sleep_hours": round(sleep, 1),
        "sleep_last": round(sleep_prev, 1),
        "workouts_min": round(workout_minutes(connection=connection, start=start, end=end)),
    }


@app.get("/api/widgets/workouts")
def widget_workouts(
    settings: Annotated[Settings, Depends(get_settings)],
    connection=Depends(warehouse),
    x_api_key: Annotated[str | None, Header()] = None,
    api_key: Annotated[str | None, Query()] = None,
) -> dict:
    require_api_key(settings=settings, x_api_key=x_api_key, api_key=api_key)
    start, end, _, _ = parse_range(range_key="14d", tz_name=settings.fitness_tz)
    rows = connection.execute(
        """
        SELECT local_date, exercise_name, CAST(duration_sec / 60 AS INTEGER) AS minutes, avg_hr
        FROM workouts
        WHERE local_date >= ? AND local_date <= ?
        ORDER BY start_utc DESC
        LIMIT 8
        """,
        (start, end),
    ).fetchall()
    return {"workouts": [dict(row) for row in rows]}


@app.get("/api/widgets/sleep")
def widget_sleep(
    settings: Annotated[Settings, Depends(get_settings)],
    connection=Depends(warehouse),
    x_api_key: Annotated[str | None, Header()] = None,
    api_key: Annotated[str | None, Query()] = None,
) -> dict:
    require_api_key(settings=settings, x_api_key=x_api_key, api_key=api_key)
    row = connection.execute(
        """
        SELECT local_date, duration_sec, light_sec, deep_sec, rem_sec, awake_sec
        FROM sleep_sessions
        ORDER BY start_utc DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return {"last_night_hours": None, "light_hours": None, "deep_hours": None, "rem_hours": None, "date": None}
    return {
        "date": row["local_date"],
        "last_night_hours": round(row["duration_sec"] / 3600, 1),
        "light_hours": round(row["light_sec"] / 3600, 1),
        "deep_hours": round(row["deep_sec"] / 3600, 1),
        "rem_hours": round(row["rem_sec"] / 3600, 1),
        "awake_hours": round(row["awake_sec"] / 3600, 1),
    }


STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/{full_path:path}")
def spa(full_path: str):
    if not STATIC_DIR.exists():
        raise HTTPException(status_code=404, detail="UI not built")
    candidate = STATIC_DIR / full_path
    if full_path and candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(STATIC_DIR / "index.html")
