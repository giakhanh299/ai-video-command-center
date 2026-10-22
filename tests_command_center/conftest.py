from __future__ import annotations

import json
import os
import secrets
import subprocess
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest
from fastapi.testclient import TestClient

from command_center.api import create_app
from command_center.cli import enroll_agent, import_input
from command_center.db import Database
from command_center.repository import Repository
from command_center.settings import Settings


@pytest.fixture(scope="session")
def test_database():
    config_path = os.environ.get("CC_TEST_CONFIG")
    if not config_path:
        pytest.skip("CC_TEST_CONFIG required for real PostgreSQL integration tests")
    config = json.loads(Path(config_path).read_text())
    base = urlsplit(config["database_url"])
    if base.hostname != "127.0.0.1" or base.port != 55439 or base.path != "/command_center_dev":
        raise RuntimeError("Tests require the dedicated loopback development database")
    name = "cc_test_" + uuid4().hex
    url = urlunsplit(base._replace(path="/" + name))
    with psycopg.connect(config["database_url"], autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
    db = Database(url)
    db.migrate()
    try:
        yield db
    finally:
        assert name.startswith("cc_test_") and len(name) == 40
        with psycopg.connect(config["database_url"], autocommit=True) as admin:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


@pytest.fixture(scope="session")
def source_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("command-center-media") / "source.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x240:rate=24:duration=0.5",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5", "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True, timeout=30)
    return path


@pytest.fixture
def env(test_database, tmp_path):
    with test_database.connect() as c:
        c.execute("TRUNCATE command_center.projects,command_center.agents,command_center.idempotency_keys CASCADE")
    settings = Settings(database_url=test_database.url, owner_token=secrets.token_urlsafe(40), owner_id=uuid4(), storage_root=tmp_path / "storage")
    client = TestClient(create_app(settings), raise_server_exceptions=False)
    token, aid, machine = secrets.token_urlsafe(40), uuid4(), uuid4()
    enroll_agent(settings, aid, machine, token)
    return {"settings": settings, "db": test_database, "repo": Repository(test_database, settings), "client": client,
            "owner": {"Authorization": "Bearer " + settings.owner_token},
            "agent": {"Authorization": "Bearer " + token}, "aid": aid, "machine": machine}


@pytest.fixture
def prepared(env, source_video):
    e = env
    response = e["client"].post("/api/v1/projects", headers={**e["owner"], "Idempotency-Key": "project-seed"}, json={"name": "Dự án kiểm thử"})
    assert response.status_code == 201, response.text
    p = response.json()
    fid = import_input(e["settings"], p["id"], source_video)
    e.update(project=p, input_id=str(fid))
    return e
