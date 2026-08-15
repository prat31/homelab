from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app.config import Settings

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
SQLITE_SUFFIXES = (".db", ".sqlite", ".sqlite3")


def is_drive_configured(*, settings: Settings) -> bool:
    has_oauth = bool(
        settings.google_oauth_client_id
        and settings.google_oauth_client_secret
        and settings.google_oauth_refresh_token
    )
    has_sa = bool(settings.google_service_account_json)
    return bool(settings.drive_folder_id) and (has_oauth or has_sa)


def build_credentials(*, settings: Settings) -> Credentials:
    if settings.google_service_account_json:
        sa_path = Path(settings.google_service_account_json)
        if sa_path.exists():
            return service_account.Credentials.from_service_account_file(
                str(sa_path), scopes=[DRIVE_SCOPE]
            )
        payload = json.loads(settings.google_service_account_json)
        return service_account.Credentials.from_service_account_info(payload, scopes=[DRIVE_SCOPE])

    credentials = Credentials(
        token=None,
        refresh_token=settings.google_oauth_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=[DRIVE_SCOPE],
    )
    credentials.refresh(Request())
    return credentials


def drive_service(*, settings: Settings):
    return build("drive", "v3", credentials=build_credentials(settings=settings), cache_discovery=False)


def list_export_files(*, settings: Settings) -> list[dict[str, Any]]:
    service = drive_service(settings=settings)
    query = f"'{settings.drive_folder_id}' in parents and trashed = false"
    files: list[dict[str, Any]] = []
    page_token = None
    while True:
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, md5Checksum, size, modifiedTime, mimeType)",
                pageToken=page_token,
                pageSize=100,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        for item in response.get("files", []):
            name = (item.get("name") or "").lower()
            if name.endswith(SQLITE_SUFFIXES) or "health" in name:
                files.append(item)
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    files.sort(key=lambda item: item.get("modifiedTime") or "", reverse=True)
    return files


def download_file(*, settings: Settings, file_id: str, dest_path: Path) -> Path:
    service = drive_service(settings=settings)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with dest_path.open("wb") as handle:
        downloader = MediaIoBaseDownload(handle, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return dest_path


def sha256_file(*, path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_hash_for_drive_file(*, drive_file: dict[str, Any], local_path: Path) -> str:
    md5 = drive_file.get("md5Checksum")
    if md5:
        return f"md5:{md5}"
    return f"sha256:{sha256_file(path=local_path)}"


def run_oauth_setup(*, client_id: str, client_secret: str) -> str:
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=[DRIVE_SCOPE])
    credentials = flow.run_local_server(port=0)
    if not credentials.refresh_token:
        raise RuntimeError("Google did not return a refresh token. Revoke access and retry.")
    return credentials.refresh_token
