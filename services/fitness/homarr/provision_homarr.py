"""Insert Fitness custom widgets and an app tile into Homarr's SQLite DB."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

HOMARR_DB = Path("/Volumes/homelab_data/homelab/data/homarr/db/db.sqlite")
WIDGET_DIR = Path(__file__).resolve().parent
BOARD_ID = "j55190to8bcepnlr8z8znsnn"
SECTION_ID = "x2s04f7m9ydjxbffwglhtky1"
LAYOUT_ID = "tsozx04cqk9y7q06ysfsxrrd"
CREATOR_ID = "yllugmv2h2lyj0tzukmr14bo"
BASE_URL = "https://fitness.homelab.pratcode.dev"


def upsert_widget(*, connection: sqlite3.Connection, payload: dict, api_key: str) -> None:
    widget_id = payload["id"]
    url = payload["url"]
    if api_key:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}api_key={api_key}"
    now = int(time.time())
    display_config = json.dumps({"json": payload["displayConfig"]})
    connection.execute(
        """
        INSERT INTO custom_widget_definition (
            id, name, description, icon_url, url, auth_type, header_name, method,
            request_body, display_type, display_config, enabled, created_at, updated_at, creator_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, 1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            description = excluded.description,
            url = excluded.url,
            auth_type = excluded.auth_type,
            header_name = excluded.header_name,
            display_type = excluded.display_type,
            display_config = excluded.display_config,
            updated_at = excluded.updated_at
        """,
        (
            widget_id,
            payload["name"],
            payload.get("description"),
            payload.get("iconUrl"),
            url,
            "none",
            None,
            payload.get("method", "GET"),
            payload.get("displayType", "keyValue"),
            display_config,
            now,
            now,
            CREATOR_ID,
        ),
    )


def upsert_item(*, connection: sqlite3.Connection, item_id: str, kind: str, options: dict, x: int, y: int, w: int, h: int) -> None:
    connection.execute(
        """
        INSERT INTO item (id, board_id, kind, options, advanced_options)
        VALUES (?, ?, ?, ?, '{"json": {}}')
        ON CONFLICT(id) DO UPDATE SET options = excluded.options
        """,
        (item_id, BOARD_ID, kind, json.dumps({"json": options})),
    )
    connection.execute(
        """
        INSERT INTO item_layout (item_id, section_id, layout_id, x_offset, y_offset, width, height)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(item_id, section_id, layout_id) DO UPDATE SET
            x_offset = excluded.x_offset,
            y_offset = excluded.y_offset,
            width = excluded.width,
            height = excluded.height
        """,
        (item_id, SECTION_ID, LAYOUT_ID, x, y, w, h),
    )


def main() -> None:
    api_key = Path("/Users/prat/Desktop/repos/homelab/.env").read_text()
    key = ""
    for line in api_key.splitlines():
        if line.startswith("FITNESS_API_KEY="):
            key = line.split("=", 1)[1].strip()

    connection = sqlite3.connect(HOMARR_DB)
    try:
        for path in sorted(WIDGET_DIR.glob("fitness-*.json")):
            upsert_widget(connection=connection, payload=json.loads(path.read_text()), api_key=key)

        connection.execute(
            """
            INSERT INTO app (id, name, description, icon_url, href, ping_url)
            VALUES ('fitness-app', 'Fitness', 'Health Connect dashboard', ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET href = excluded.href, ping_url = excluded.ping_url
            """,
            (
                "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons@master/svg/garmin.svg",
                BASE_URL,
                BASE_URL,
            ),
        )
        upsert_item(
            connection=connection,
            item_id="fitness-app-tile",
            kind="app",
            options={"appId": "fitness-app", "openInNewTab": True, "showTitle": True},
            x=8,
            y=5,
            w=1,
            h=1,
        )
        upsert_item(
            connection=connection,
            item_id="fitness-overview-tile",
            kind="customApi",
            options={"definitionId": "fitness-overview", "refreshInterval": 300},
            x=0,
            y=5,
            w=4,
            h=1,
        )
        upsert_item(
            connection=connection,
            item_id="fitness-week-tile",
            kind="customApi",
            options={"definitionId": "fitness-week", "refreshInterval": 300},
            x=4,
            y=5,
            w=2,
            h=1,
        )
        upsert_item(
            connection=connection,
            item_id="fitness-sleep-tile",
            kind="customApi",
            options={"definitionId": "fitness-sleep", "refreshInterval": 300},
            x=6,
            y=5,
            w=2,
            h=1,
        )
        connection.commit()
        print("Homarr widgets and Fitness app tile upserted")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
