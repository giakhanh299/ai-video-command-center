"""Explicit maintenance commands; never migrate or enroll Agents at API startup."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import importlib.util
from pathlib import Path
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from .db import Database
from .errors import DomainError
from .registry import MODULE_VERSION
from .repository import project
from .settings import Settings
from .storage import checksum, storage_path, verify_file


def enroll_agent(settings, agent_id, machine_id, token):
    if len(token) < 32 or token == settings.owner_token:
        raise DomainError("INVALID_AGENT_CREDENTIAL", 422)
    capabilities = []
    if shutil.which("ffprobe"):
        capabilities.append("media.probe@" + MODULE_VERSION)
        if shutil.which("ffmpeg") and all(importlib.util.find_spec(m) for m in ("cv2", "numpy")):
            capabilities.append("render.basic@" + MODULE_VERSION)
    with Database(settings.database_url).connect() as c:
        result = c.execute("INSERT INTO command_center.agents(id,owner_id,machine_id,credential_hash,capabilities,capability_version) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET credential_hash=EXCLUDED.credential_hash,capabilities=EXCLUDED.capabilities,capability_version=EXCLUDED.capability_version WHERE command_center.agents.owner_id=EXCLUDED.owner_id AND command_center.agents.machine_id=EXCLUDED.machine_id",
                  (agent_id, settings.owner_id, machine_id, hashlib.sha256(token.encode()).hexdigest(),
                   Jsonb(capabilities), MODULE_VERSION))
        if result.rowcount != 1:
            raise DomainError("AGENT_SCOPE", 403)


def import_input(settings, project_id, source):
    source = Path(source).resolve()
    if not source.is_file() or source.suffix.lower() != ".mp4":
        raise DomainError("INVALID_VIDEO", 422)
    fid = uuid4()
    key = f"inputs/{fid}.mp4"
    target = storage_path(settings.storage_root, key)
    row = {"id": fid, "project_id": project_id, "logical_name": f"{fid}.mp4", "kind": "video", "media_type": "video/mp4",
           "size_bytes": source.stat().st_size, "sha256": checksum(source), "storage_key": key}
    # Validate source first; all writes are to a fresh file in managed storage.
    from .storage import inspect_video
    inspect_video(source)
    if not 0 < row["size_bytes"] <= 524288000:
        raise DomainError("INVALID_FILE_SIZE", 422)
    with Database(settings.database_url).connect() as c:
        p = project(c, settings.owner_id, project_id, True)
        if p["archived_at"]:
            raise DomainError("PROJECT_ARCHIVED")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with source.open("rb") as src, target.open("xb") as dst:
                shutil.copyfileobj(src, dst)
            verify_file(settings.storage_root, row)
            c.execute("INSERT INTO command_center.files(id,project_id,logical_name,kind,media_type,size_bytes,sha256,storage_key,verification) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'verified')", tuple(row[k] for k in ("id", "project_id", "logical_name", "kind", "media_type", "size_bytes", "sha256", "storage_key")))
        except Exception:
            target.unlink(missing_ok=True)
            raise
    return fid


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    enroll = sub.add_parser("enroll-agent")
    enroll.add_argument("--agent-id", type=UUID, required=True)
    enroll.add_argument("--machine-id", type=UUID, required=True)
    enroll.add_argument("--token-env", default="CC_AGENT_TOKEN")
    imp = sub.add_parser("import-input")
    imp.add_argument("--project-id", type=UUID, required=True)
    imp.add_argument("--path", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings.load()
    try:
        if args.command == "migrate":
            Database(settings.database_url).migrate()
            print("Migration completed")
        elif args.command == "enroll-agent":
            enroll_agent(settings, args.agent_id, args.machine_id, os.environ.get(args.token_env, ""))
            print("Agent credential enrolled; token not printed")
        else:
            print(json.dumps({"file_id": str(import_input(settings, args.project_id, args.path))}))
    except Exception as exc:
        # Driver exceptions can contain DSNs or SQL parameters.
        print(json.dumps({"error": exc.code if isinstance(exc, DomainError) else "MAINTENANCE_FAILED"}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
