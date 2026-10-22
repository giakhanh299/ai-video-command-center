import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from fastapi.testclient import TestClient

from command_center.api import create_app
from command_center.repository import Repository
from command_center.storage import checksum
from test_postgres_api import new_job, claim


def test_concurrent_idempotent_job_creation_is_single_resource(prepared):
    e = prepared
    with ThreadPoolExecutor(max_workers=4) as workers:
        results = list(workers.map(lambda _: new_job(e), range(4)))
    assert all(r.status_code == 201 for r in results)
    assert len({r.json()["id"] for r in results}) == 1
    with e["db"].connect() as c:
        assert c.execute("SELECT count(*) AS n FROM command_center.jobs").fetchone()["n"] == 1


def test_new_api_instance_keeps_job_and_input_in_postgres(prepared):
    e = prepared
    job = new_job(e).json()
    restarted = TestClient(create_app(e["settings"]), raise_server_exceptions=False)
    assert restarted.get("/api/v1/jobs/" + job["id"], headers=e["owner"]).json()["status"] == "queued"
    assert restarted.get("/api/v1/files/" + e["input_id"] + "/content", headers=e["owner"]).status_code == 200


def test_running_cancel_does_not_publish_success_or_release_uncertain_resource(prepared):
    e = prepared
    job = new_job(e).json()
    t = claim(e).json()
    current = e["client"].get("/api/v1/jobs/" + job["id"], headers=e["owner"]).json()
    cancelled = e["client"].post(f"/api/v1/jobs/{job['id']}/cancel", headers=e["owner"], json={"expected_version": current["version"]}).json()
    assert cancelled["status"] == "cancelling"
    lease = {"attempt": t["attempt"], "lease_token": t["lease_token"]}
    path = f"/api/v1/agent/tasks/{t['task']['id']}"
    assert e["client"].post(path + "/renew", headers=e["agent"], json=lease).json()["cancel_requested"]
    body = {**lease, "status": "succeeded", "output_ids": [], "error_code": None, "stop_receipt_id": None}
    assert e["client"].post(path + "/complete", headers=e["agent"], json=body).json()["error"]["code"] == "CANCEL_REQUIRES_RECONCILIATION"
    body.update(status="needs_attention", error_code="CANCEL_REQUIRES_RECONCILIATION")
    assert e["client"].post(path + "/complete", headers=e["agent"], json=body).status_code == 200
    assert claim(e).json()["error"]["code"] == "RESOURCE_BUSY"


def test_file_registration_and_completion_verify_actual_bytes_and_roles(prepared):
    e = prepared
    new_job(e)
    t = claim(e).json()
    tid = t["task"]["id"]
    key = f"attempts/{tid}/{t['attempt']}/probe.json"
    path = e["settings"].storage_root / key
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema_version": "1.0.0", "media": {"fake": True}}))
    body = {"attempt": t["attempt"], "lease_token": t["lease_token"], "project_id": e["project"]["id"],
            "job_id": t["manifest"]["job_id"], "task_id": tid, "logical_name": "probe.json", "kind": "report", "media_type": "application/json",
            "size_bytes": path.stat().st_size, "sha256": "0" * 64, "storage_key": key}
    assert e["client"].post("/api/v1/agent/files", headers=e["agent"], json=body).json()["error"]["code"] == "FILE_INTEGRITY_MISMATCH"
    body["sha256"] = checksum(path)
    fid = e["client"].post("/api/v1/agent/files", headers=e["agent"], json=body).json()["id"]
    done = {"attempt": t["attempt"], "lease_token": t["lease_token"], "status": "succeeded", "output_ids": [fid], "error_code": None, "stop_receipt_id": None}
    assert e["client"].post(f"/api/v1/agent/tasks/{tid}/complete", headers=e["agent"], json=done).json()["error"]["code"] == "OUTPUT_UNVERIFIED"
    body["storage_key"] = "../escape.json"
    assert e["client"].post("/api/v1/agent/files", headers=e["agent"], json=body).status_code == 422


def test_attempt_fencing_rejects_wrong_token_and_logs_are_sanitized(prepared):
    e = prepared
    job = new_job(e).json()
    t = claim(e).json()
    lease = {"attempt": t["attempt"], "lease_token": str(uuid4())}
    path = f"/api/v1/agent/tasks/{t['task']['id']}"
    assert e["client"].post(path + "/renew", headers=e["agent"], json=lease).json()["error"]["code"] == "STALE_LEASE"
    lease["lease_token"] = t["lease_token"]
    secret = "Bearer TOP_SECRET_SENT_BY_AGENT"
    body = {**lease, "event_id": str(uuid4()), "level": "warning", "code": "TASK_WARNING", "message": secret}
    response = e["client"].post(path + "/events", headers=e["agent"], json=body)
    assert response.status_code == 201 and secret not in response.text
    assert secret not in e["client"].get(f"/api/v1/jobs/{job['id']}/events", headers=e["owner"]).text


def test_retry_budget_cannot_be_reset_by_request(prepared):
    e = prepared
    job = new_job(e).json()
    with e["db"].connect() as c:
        c.execute("UPDATE command_center.jobs SET status='failed' WHERE id=%s", (job["id"],))
        c.execute("UPDATE command_center.tasks SET status='failed',attempt=3 WHERE job_id=%s", (job["id"],))
    response = e["client"].post(f"/api/v1/jobs/{job['id']}/retry", headers={**e["owner"], "Idempotency-Key": "retry-over-budget"}, json={"expected_version": job["version"]})
    assert response.json()["error"]["code"] == "RETRY_LIMIT"


def test_real_pg_dump_restore_preserves_project_job_and_file_metadata(prepared):
    e = prepared
    job = new_job(e).json()
    source_db = urlsplit(e["db"].url).path[1:]
    assert source_db.startswith("cc_test_") and len(source_db) == 40
    restore_db = "cc_restore_" + uuid4().hex
    container = "ai-video-command-center-postgres-dev"
    dump = subprocess.run(["docker", "exec", container, "pg_dump", "-U", "ccdev", "-Fc", "--no-owner", source_db], capture_output=True, timeout=30)
    assert dump.returncode == 0 and dump.stdout.startswith(b"PGDMP"), "pg_dump failed"
    with psycopg.connect(e["db"].url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(restore_db)))
    try:
        restored = subprocess.run(["docker", "exec", "-i", container, "pg_restore", "-U", "ccdev", "--no-owner", "--exit-on-error", "-d", restore_db], input=dump.stdout, capture_output=True, timeout=30)
        assert restored.returncode == 0, "pg_restore failed"
        from command_center.db import Database
        url = urlunsplit(urlsplit(e["db"].url)._replace(path="/" + restore_db))
        restored_repo = Repository(Database(url), e["settings"])
        value = restored_repo.get_job(e["settings"].owner_id, UUID(job["id"]))
        assert str(value["id"]) == job["id"] and value["status"] == "queued"
        with Database(url).connect() as c:
            row = c.execute("SELECT * FROM command_center.files WHERE id=%s", (e["input_id"],)).fetchone()
            assert row["verification"] == "verified"
            from command_center.storage import verify_file
            assert verify_file(e["settings"].storage_root, row).is_file()
    finally:
        assert restore_db.startswith("cc_restore_") and len(restore_db) == 43
        with psycopg.connect(e["db"].url, autocommit=True) as admin:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (restore_db,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(restore_db)))
