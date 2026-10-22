from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from command_center.agent import run_once
from command_center.api import create_app
from command_center.cli import enroll_agent
from command_center.models import ClaimRequest
from command_center.registry import MODULE_VERSION


def new_job(e, preset="inspect_media", key="job-create-1"):
    return e["client"].post("/api/v1/jobs", headers={**e["owner"], "Idempotency-Key": key}, json={
        "schema_version": "0.1.0-draft", "project_id": e["project"]["id"], "preset_id": preset,
        "preset_version": MODULE_VERSION, "input_refs": [e["input_id"]], "overrides": {}})


def claim(e):
    return e["client"].post("/api/v1/agent/claims", headers=e["agent"], json={"agent_id": str(e["aid"]), "resource": "cpu:0"})


def test_health_auth_readiness_and_separate_agent_scope(env):
    c = env["client"]
    assert c.get("/api/v1/health").status_code == 200
    assert c.get("/api/v1/projects").status_code == 401
    assert c.get("/api/v1/ready", headers=env["owner"]).status_code == 200
    assert c.get("/api/v1/projects", headers=env["agent"]).status_code == 401
    assert c.post("/api/v1/agent/claims", headers=env["owner"], json={"agent_id": str(env["aid"]), "resource": "cpu:0"}).status_code == 401


def test_database_outage_fails_closed_without_fallback(env):
    settings = replace(env["settings"], database_url="postgresql://invalid:invalid@127.0.0.1:1/unavailable")
    c = TestClient(create_app(settings), raise_server_exceptions=False)
    result = c.get("/api/v1/ready", headers=env["owner"])
    assert result.status_code == 503
    assert "invalid:" not in result.text
    assert c.post("/api/v1/projects", headers={**env["owner"], "Idempotency-Key": "failure-case"}, json={"name": "No RAM fallback"}).status_code == 503


def test_project_idempotency_versions_pagination_and_ownership(env):
    c, h = env["client"], {**env["owner"], "Idempotency-Key": "same-project"}
    a = c.post("/api/v1/projects", headers=h, json={"name": "A"})
    assert a.status_code == 201
    assert c.post("/api/v1/projects", headers=h, json={"name": "A"}).json()["id"] == a.json()["id"]
    assert c.post("/api/v1/projects", headers=h, json={"name": "B"}).status_code == 409
    pid = a.json()["id"]
    assert c.patch(f"/api/v1/projects/{pid}", headers=env["owner"], json={"name": "A2", "expected_version": 1}).status_code == 200
    assert c.patch(f"/api/v1/projects/{pid}", headers=env["owner"], json={"name": "A3", "expected_version": 1}).status_code == 409
    other = TestClient(create_app(replace(env["settings"], owner_id=uuid4())), raise_server_exceptions=False)
    assert other.get(f"/api/v1/projects/{pid}", headers=env["owner"]).status_code == 404
    for i in range(3):
        c.post("/api/v1/projects", headers={**env["owner"], "Idempotency-Key": f"project-{i}"}, json={"name": str(i)})
    first = c.get("/api/v1/projects?limit=2", headers=env["owner"]).json()
    second = c.get("/api/v1/projects", params={"limit": 2, "cursor": first["next_cursor"]}, headers=env["owner"]).json()
    assert len(first["items"]) == len(second["items"]) == 2
    assert not {p["id"] for p in first["items"]} & {p["id"] for p in second["items"]}


def test_offline_agent_does_not_lose_or_fail_job(prepared):
    e = prepared
    result = new_job(e)
    assert result.status_code == 201, result.text
    assert result.json()["status"] == "queued"
    assert e["client"].get("/api/v1/agents", headers=e["owner"]).json()["items"][0]["status"] == "offline"
    assert e["client"].get("/api/v1/jobs/" + result.json()["id"], headers=e["owner"]).json()["status"] == "queued"
    assert new_job(e).json()["id"] == result.json()["id"]
    other = TestClient(create_app(replace(e["settings"], owner_id=uuid4())), raise_server_exceptions=False)
    assert other.get("/api/v1/jobs/" + result.json()["id"], headers=e["owner"]).status_code == 404


def test_invalid_module_and_tampered_input_rejected(prepared):
    e = prepared
    assert new_job(e, "wuby").json()["error"]["code"] == "MODULE_NOT_READY"
    assert new_job(e, "unregistered").status_code == 422
    with e["db"].connect() as c:
        c.execute("UPDATE command_center.files SET sha256=%s", ("0" * 64,))
    assert new_job(e).json()["error"]["code"] == "FILE_INTEGRITY_MISMATCH"


def test_competing_claims_and_host_resource_fencing(prepared):
    e = prepared
    new_job(e)
    agent = e["repo"].agent_by_token(e["agent"]["Authorization"].split()[1])
    request = ClaimRequest(agent_id=e["aid"], resource="cpu:0")
    def attempt(_):
        try:
            return e["repo"].claim(agent, request)
        except Exception as exc:
            return getattr(exc, "code", "unexpected")
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))
    assert sum(isinstance(v, dict) for v in results) == 1
    assert all(isinstance(v, dict) or v == "RESOURCE_BUSY" for v in results)
    token, aid = "b" * 40, uuid4()
    enroll_agent(e["settings"], aid, e["machine"], token)
    response = e["client"].post("/api/v1/agent/claims", headers={"Authorization": "Bearer " + token}, json={"agent_id": str(aid), "resource": "cpu:0"})
    assert response.json()["error"]["code"] == "RESOURCE_BUSY"


def test_expired_lease_is_quarantined_not_replayed(prepared):
    e = prepared
    job = new_job(e).json()
    received = claim(e).json()
    with e["db"].connect() as c:
        c.execute("UPDATE command_center.tasks SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s", (received["task"]["id"],))
    state = e["client"].get("/api/v1/jobs/" + job["id"], headers=e["owner"]).json()
    assert state["status"] == "needs_attention"
    assert claim(e).json()["error"]["code"] == "RESOURCE_BUSY"
    retry = e["client"].post(f"/api/v1/jobs/{job['id']}/retry", headers={**e["owner"], "Idempotency-Key": "retry-expired"}, json={"expected_version": state["version"]})
    assert retry.json()["error"]["code"] == "RECONCILIATION_REQUIRED"
    complete = {"attempt": received["attempt"], "lease_token": received["lease_token"], "status": "succeeded", "output_ids": [], "error_code": None, "stop_receipt_id": None}
    assert e["client"].post(f"/api/v1/agent/tasks/{received['task']['id']}/complete", headers=e["agent"], json=complete).json()["error"]["code"] == "STALE_LEASE"


def test_cancel_queued_and_idempotent_retry(prepared):
    e = prepared
    job = new_job(e).json()
    canceled = e["client"].post(f"/api/v1/jobs/{job['id']}/cancel", headers=e["owner"], json={"expected_version": job["version"]}).json()
    assert canceled["status"] == "cancelled"
    assert claim(e).status_code == 204
    path = f"/api/v1/jobs/{job['id']}/retry"
    headers = {**e["owner"], "Idempotency-Key": "retry-cancelled"}
    first = e["client"].post(path, headers=headers, json={"expected_version": canceled["version"]})
    assert first.status_code == 202
    assert e["client"].post(path, headers=headers, json={"expected_version": canceled["version"]}).json()["id"] == job["id"]


def test_validation_redacts_client_input_and_limits_body(env):
    secret = "private-token-not-to-echo"
    response = env["client"].post("/api/v1/projects", headers={**env["owner"], "Idempotency-Key": "invalid-body"}, json={"name": "A", "password": secret})
    assert response.status_code == 422 and secret not in response.text
    assert env["client"].post("/api/v1/projects", headers=env["owner"], content=b"x" * (256 * 1024 + 1)).status_code == 413


def test_completed_task_requires_verified_output_and_cannot_fake_cancel(prepared):
    e = prepared
    new_job(e)
    t = claim(e).json()
    body = {"attempt": t["attempt"], "lease_token": t["lease_token"], "status": "succeeded", "output_ids": [], "error_code": None, "stop_receipt_id": None}
    path = f"/api/v1/agent/tasks/{t['task']['id']}/complete"
    assert e["client"].post(path, headers=e["agent"], json=body).json()["error"]["code"] == "OUTPUT_UNVERIFIED"
    body["status"] = "cancelled"
    assert e["client"].post(path, headers=e["agent"], json=body).json()["error"]["code"] == "STOP_NOT_VERIFIED"


def test_real_cpu_render_through_postgres_queue_and_agent(prepared):
    e = prepared
    job = new_job(e, "basic_render").json()
    agent_client = TestClient(create_app(e["settings"]), headers=e["agent"], raise_server_exceptions=False)
    assert run_once(agent_client, e["aid"], e["settings"].storage_root)["status"] == "succeeded"
    interim = e["client"].get("/api/v1/jobs/" + job["id"], headers=e["owner"]).json()
    assert interim["status"] == "running" and interim["progress"]["completed_tasks"] == 1
    assert run_once(agent_client, e["aid"], e["settings"].storage_root)["status"] == "succeeded"
    final = e["client"].get("/api/v1/jobs/" + job["id"], headers=e["owner"]).json()
    assert final["status"] == "needs_review" and final["progress"]["completed_tasks"] == 2
    outputs = e["client"].get(f"/api/v1/jobs/{job['id']}/outputs", headers=e["owner"]).json()["items"]
    videos = [o for o in outputs if o["kind"] == "video"]
    assert len(videos) == 1 and videos[0]["verification"] == "verified"
    fid = videos[0]["id"]
    assert e["client"].get(f"/api/v1/files/{fid}/content").status_code == 401
    assert e["client"].get(f"/api/v1/files/{fid}/content", headers={**e["owner"], "Range": "bytes=0-63"}).status_code == 206
    assert run_once(agent_client, e["aid"], e["settings"].storage_root)["status"] == "idle"
    with e["db"].connect() as c:
        task = c.execute("SELECT * FROM command_center.tasks WHERE job_id=%s AND module='render.basic'", (job["id"],)).fetchone()
    body = {"attempt": task["attempt"], "lease_token": str(task["lease_token"]), "status": "succeeded",
            "output_ids": task["output_refs"], "error_code": None, "stop_receipt_id": None}
    path = f"/api/v1/agent/tasks/{task['id']}/complete"
    assert agent_client.post(path, json=body).status_code == 200
    body["status"] = "failed"
    assert agent_client.post(path, json=body).json()["error"]["code"] == "COMPLETION_CONFLICT"


def test_heartbeat_checks_attempt_scope(prepared):
    e = prepared
    new_job(e)
    received = claim(e).json()
    body = {"agent_id": str(e["aid"]), "capability_version": "1.0.0", "active_attempt_ids": [str(uuid4())]}
    assert e["client"].post("/api/v1/agent/heartbeat", headers=e["agent"], json=body).json()["error"]["code"] == "ATTEMPT_SCOPE"
    body["active_attempt_ids"] = [received["attempt_id"]]
    assert e["client"].post("/api/v1/agent/heartbeat", headers=e["agent"], json=body).status_code == 200
