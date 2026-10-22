"""Upload rendered files to Google Drive and return a clickable web link."""

from __future__ import annotations

import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Optional

import requests


PROJECT_DIR = Path(__file__).resolve().parent.parent
TOKEN_FILE = PROJECT_DIR / "gdrive_token.json"
DRIVE_ROOT_FOLDER_ID = os.getenv(
    "GDRIVE_ROOT_FOLDER_ID", "1fV0GyTCBblUHQIpJ1Kzsh6rho8oYwY8b"
).strip()


def _access_token() -> str:
    data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": data["client_id"],
            "client_secret": data["client_secret"],
            "refresh_token": data["refresh_token"],
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _escape_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _find_child(token: str, parent_id: str, name: str, folder_only: bool = False) -> Optional[dict]:
    query = f"'{parent_id}' in parents and name = '{_escape_query(name)}' and trashed = false"
    if folder_only:
        query += " and mimeType = 'application/vnd.google-apps.folder'"
    response = requests.get(
        "https://www.googleapis.com/drive/v3/files",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "q": query,
            "fields": "files(id,name,mimeType,webViewLink,modifiedTime,size)",
            "orderBy": "modifiedTime desc",
            "pageSize": 20,
        },
        timeout=20,
    )
    response.raise_for_status()
    files = response.json().get("files", [])
    return files[0] if files else None


def _ensure_folder(token: str, parent_id: str, name: str) -> str:
    existing = _find_child(token, parent_id, name, folder_only=True)
    if existing:
        return existing["id"]
    response = requests.post(
        "https://www.googleapis.com/drive/v3/files",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        },
        params={"fields": "id"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["id"]


def _ensure_folder_path(token: str, relative_folder: str) -> str:
    parent_id = DRIVE_ROOT_FOLDER_ID
    for part in Path(relative_folder.replace("\\", "/")).parts:
        clean = str(part).strip(" /\\")
        if clean and clean != ".":
            parent_id = _ensure_folder(token, parent_id, clean)
    return parent_id


def upload_and_get_link(file_path: str | Path, relative_folder: str) -> str:
    """Return the existing Drive URL or upload the file and return its webViewLink."""
    source = Path(file_path)
    if not source.is_file() or source.stat().st_size <= 0:
        raise FileNotFoundError(f"Rendered file is missing or empty: {source}")

    token = _access_token()
    parent_id = _ensure_folder_path(token, relative_folder)
    existing = _find_child(token, parent_id, source.name)
    if existing and int(existing.get("size") or 0) == source.stat().st_size:
        return existing.get("webViewLink") or f"https://drive.google.com/file/d/{existing['id']}/view"

    metadata = {"name": source.name}
    if not existing:
        metadata["parents"] = [parent_id]
    upload_url = "https://www.googleapis.com/upload/drive/v3/files"
    upload_method = requests.post
    if existing:
        upload_url += f"/{existing['id']}"
        upload_method = requests.patch
    init = upload_method(
        upload_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": mimetypes.guess_type(source.name)[0] or "application/octet-stream",
            "X-Upload-Content-Length": str(source.stat().st_size),
        },
        params={"uploadType": "resumable", "fields": "id,name,webViewLink,size"},
        json=metadata,
        timeout=30,
    )
    init.raise_for_status()
    session_url = init.headers["Location"]

    with source.open("rb") as stream:
        uploaded = requests.put(
            session_url,
            headers={"Content-Type": mimetypes.guess_type(source.name)[0] or "application/octet-stream"},
            data=stream,
            timeout=3600,
        )
    uploaded.raise_for_status()
    item = uploaded.json()
    file_id = item["id"]
    return item.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view"


def wait_for_link(file_path: str | Path, relative_folder: str, attempts: int = 3) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(max(1, attempts)):
        try:
            return upload_and_get_link(file_path, relative_folder)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Không thể tạo link Google Drive: {last_error}")
