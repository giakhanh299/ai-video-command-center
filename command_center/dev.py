"""Local development tools for the separately labelled PostgreSQL container."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID

from .db import Database
from .errors import DomainError
from .settings import Settings

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "workspace/command_center_dev"
CONFIG = DEV / "credentials.local.json"
CONTAINER = "ai-video-command-center-postgres-dev"


def local_settings(values):
    # Never let an inherited production CC_DATABASE_URL redirect dev migrations.
    return Settings(database_url=values["database_url"], owner_token=values["owner_token"],
                    owner_id=UUID(values["owner_id"]), storage_root=Path(values["storage_root"]))


def configuration():
    DEV.mkdir(parents=True, exist_ok=True)
    if CONFIG.exists():
        values = json.loads(CONFIG.read_text(encoding="utf-8"))
    else:
        values = {"password": secrets.token_urlsafe(32), "owner_token": secrets.token_urlsafe(40),
                  "agent_token": secrets.token_urlsafe(40),
                  "owner_id": "11111111-1111-4111-8111-111111111111",
                  "agent_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                  "machine_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "port": 55439}
    values["database_url"] = "postgresql://ccdev:" + values["password"] + "@127.0.0.1:55439/command_center_dev"
    values["storage_root"] = str(DEV / "storage")
    CONFIG.write_text(json.dumps(values), encoding="utf-8")
    os.environ["CC_CONFIG_FILE"] = str(CONFIG)
    return values


def prepare():
    values = configuration()
    env_file = DEV / "postgres.env.local"
    env_file.write_text("POSTGRES_USER=ccdev\nPOSTGRES_DB=command_center_dev\nPOSTGRES_PASSWORD=" + values["password"] + "\n", encoding="utf-8")
    exists = subprocess.run(["docker", "inspect", "--format", '{{index .Config.Labels "codex.task"}}', CONTAINER], capture_output=True, text=True)
    if exists.returncode == 0:
        if exists.stdout.strip() != "ai-video-command-center":
            raise DomainError("UNEXPECTED_CONTAINER", 503)
        result = subprocess.run(["docker", "start", CONTAINER], capture_output=True)
    else:
        (DEV / "docker_pgdata").mkdir(exist_ok=True)
        result = subprocess.run(["docker", "run", "-d", "--name", CONTAINER,
            "--label", "codex.task=ai-video-command-center", "--env-file", str(env_file),
            "-p", "127.0.0.1:55439:5432", "--mount", "type=bind,source=" + str(DEV / "docker_pgdata") + ",target=/var/lib/postgresql/data",
            "postgres:16-alpine"], capture_output=True)
    if result.returncode:
        raise DomainError("DEV_DATABASE_START_FAILED", 503)
    settings = local_settings(values)
    database = Database(settings.database_url)
    for attempt in range(20):
        try:
            with database.connect() as c:
                c.execute("SELECT 1")
            break
        except Exception:
            if attempt == 19:
                raise DomainError("DEV_DATABASE_NOT_READY", 503)
            time.sleep(.5)
    database.migrate()
    from .cli import enroll_agent
    enroll_agent(settings, UUID(values["agent_id"]), UUID(values["machine_id"]), values["agent_token"])
    return settings, values


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "serve", "agent", "test"):
        sub.add_parser(name)
    imp = sub.add_parser("import-input")
    imp.add_argument("--project-id", type=UUID, required=True)
    imp.add_argument("--path", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command in ("prepare", "serve"):
            settings, values = prepare()
        else:
            values = configuration()
            settings = local_settings(values)
        if args.command == "prepare":
            print("PostgreSQL dev ready on 127.0.0.1:55439; migrations applied; Agent enrolled")
        elif args.command == "serve":
            from .api import create_app
            import uvicorn
            uvicorn.run(create_app(settings), host="127.0.0.1", port=8016, access_log=False)
        elif args.command == "agent":
            from .agent import AgentClient, run_once
            client = AgentClient("http://127.0.0.1:8016", values["agent_token"])
            print(json.dumps(run_once(client, UUID(values["agent_id"]), settings.storage_root.resolve())))
        elif args.command == "test":
            os.environ["CC_TEST_CONFIG"] = str(CONFIG)
            raise SystemExit(subprocess.call([sys.executable, "-B", "-m", "pytest", "tests_command_center", "-q", "-p", "no:cacheprovider"], cwd=ROOT))
        else:
            from .cli import import_input
            print(json.dumps({"file_id": str(import_input(settings, args.project_id, args.path))}))
    except Exception as exc:
        print(json.dumps({"error": exc.code if isinstance(exc, DomainError) else "DEV_COMMAND_FAILED"}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
