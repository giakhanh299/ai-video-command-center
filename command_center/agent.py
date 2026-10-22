"""Outbound CPU pilot Agent. Wuby/TTS/GPU are deliberately not enabled here.

Deployment model (2026-10-22): the PC opens NO inbound ports. The Agent only
initiates outbound HTTPS connections to the Command Center API on port 443
and waits for work by claiming jobs (see validate_agent_url / run_forever).
Plain HTTP is accepted solely for loopback URLs used in local development.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx

from .errors import DomainError
from .modules import execute
from .registry import MODULE_VERSION, validate_manifest
from .storage import checksum, storage_path, verify_file


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def validate_agent_url(url):
    """Enforce the outbound-only rule: remote APIs are reached over HTTPS on
    port 443 only, so the PC never needs an inbound listener or tunnel.
    Loopback URLs keep any scheme/port for local development and tests."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in LOOPBACK_HOSTS:
        if parsed.scheme in ("http", "https"):
            return url.rstrip("/")
        raise DomainError("TLS_REQUIRED", 422)
    if parsed.scheme != "https":
        raise DomainError("TLS_REQUIRED", 422)
    if parsed.port not in (None, 443):
        raise DomainError("OUTBOUND_443_ONLY", 422)
    return url.rstrip("/")


class AgentClient:
    def __init__(self, url, token):
        validate_agent_url(url)
        self.client = httpx.Client(base_url=url.rstrip("/"), headers={"Authorization": "Bearer " + token}, timeout=15, trust_env=False)

    def post(self, path, **kwargs):
        return self.client.post(path, **kwargs)


def checked(response):
    if response.status_code >= 400:
        # Never echo raw HTTP response/URL/header/transport exception to job logs.
        raise DomainError("AGENT_REQUEST_REJECTED", response.status_code)
    return response.json() if response.status_code != 204 else None




def run_once(client, agent_id, storage_root):
    checked(client.post("/api/v1/agent/heartbeat", json={"agent_id": str(agent_id), "capability_version": MODULE_VERSION, "active_attempt_ids": []}))
    response = client.post("/api/v1/agent/claims", json={"agent_id": str(agent_id), "resource": "cpu:0"})
    if response.status_code == 409 and response.json().get("error", {}).get("code") == "RESOURCE_BUSY":
        return {"status": "resource_busy"}
    claim = checked(response)
    if not claim:
        return {"status": "idle"}
    tid = claim["task"]["id"]
    lease = {"attempt": claim["attempt"], "lease_token": claim["lease_token"]}
    abort, finished = threading.Event(), threading.Event()
    completion = {**lease, "status": "needs_attention", "output_ids": [], "error_code": "EXECUTION_FAILED", "stop_receipt_id": None}

    def renew():
        while not finished.wait(10):
            try:
                checked(client.post("/api/v1/agent/heartbeat", json={"agent_id": str(agent_id), "capability_version": MODULE_VERSION, "active_attempt_ids": [claim["attempt_id"]]}))
                state = checked(client.post(f"/api/v1/agent/tasks/{tid}/renew", json=lease))
                if state["cancel_requested"]:
                    abort.set()
                    return
            except Exception:
                abort.set()
                return

    thread = threading.Thread(target=renew, daemon=True)
    try:
        manifest = validate_manifest(claim["manifest"])
        task = next(t for t in manifest.pipeline if str(t.task_id) == tid)
        if task.attempt != claim["attempt"] or task.module not in ("media.probe", "render.basic"):
            raise DomainError("MODULE_NOT_READY")
        inputs = claim.get("input_files", [])
        if len(inputs) != 1 or str(inputs[0]["id"]) not in [str(v) for v in task.input_refs]:
            raise DomainError("INPUT_CHANGED")
        source = verify_file(storage_root, inputs[0])
        state = checked(client.post(f"/api/v1/agent/tasks/{tid}/renew", json=lease))
        if state["cancel_requested"]:
            raise DomainError("CANCEL_REQUIRES_RECONCILIATION")
        checked(client.post(f"/api/v1/agent/tasks/{tid}/events", json={**lease, "event_id": str(uuid4()), "level": "info", "code": "TASK_STARTED", "message": "Task bắt đầu xử lý."}))
        thread.start()
        directory = storage_path(storage_root, f"attempts/{tid}/{claim['attempt']}")
        outputs = execute(task.module, task.config, source, directory, abort)
        state = checked(client.post(f"/api/v1/agent/tasks/{tid}/renew", json=lease))
        if abort.is_set() or state["cancel_requested"]:
            raise DomainError("CANCEL_REQUIRES_RECONCILIATION")
        registered = []
        for file, kind, mime in outputs:
            payload = {**lease, "project_id": str(manifest.project_id), "job_id": str(manifest.job_id), "task_id": tid,
                       "logical_name": file.name, "kind": kind, "media_type": mime,
                       "size_bytes": file.stat().st_size, "sha256": checksum(file),
                       "storage_key": file.relative_to(storage_root.resolve()).as_posix()}
            registered.append(checked(client.post("/api/v1/agent/files", json=payload))["id"])
        completion.update(status="succeeded", output_ids=registered, error_code=None)
    except Exception as exc:
        code = exc.code if isinstance(exc, DomainError) else "EXECUTION_FAILED"
        if code not in ("INPUT_CHANGED", "MODULE_NOT_READY", "CANCEL_REQUIRES_RECONCILIATION"):
            code = "EXECUTION_FAILED"
        completion.update(status="needs_attention", error_code=code)
    finally:
        finished.set()
        if thread.is_alive():
            thread.join(timeout=16)
    checked(client.post(f"/api/v1/agent/tasks/{tid}/complete", json=completion))
    return {"status": completion["status"], "task_id": tid}


def run_forever(client, agent_id, storage_root, poll_interval=5.0, stop_event=None, sleep=time.sleep, once=None):
    """Wait-for-commands loop: claim work over the outbound 443 connection,
    back off while idle and on failures, until stop_event is set. This is the
    normal production mode on the PC; run_once stays for tests and dev."""
    once = once or run_once
    stop_event = stop_event or threading.Event()
    failures = 0
    cycles = 0
    while not stop_event.is_set():
        cycles += 1
        try:
            result = once(client, agent_id, storage_root)
            failures = 0
            if result.get("status") in ("idle", "resource_busy"):
                sleep(poll_interval)
            else:
                sleep(min(poll_interval, 1.0))
        except Exception:
            failures += 1
            sleep(min(60.0, poll_interval * (2 ** min(failures, 4))))
    return {"status": "stopped", "cycles": cycles}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.environ.get("CC_API_URL", "http://127.0.0.1:8016"),
                        help="API base URL. Production: https://<api-host> (outbound 443 only).")
    parser.add_argument("--agent-id", type=UUID, required=True)
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--loop", action="store_true",
                        help="Run continuously waiting for commands instead of a single claim cycle.")
    parser.add_argument("--poll-interval", type=float,
                        default=float(os.environ.get("CC_AGENT_POLL_SECONDS", "5")),
                        help="Seconds to wait between claim attempts while idle (default 5).")
    args = parser.parse_args()
    token = os.environ.get("CC_AGENT_TOKEN", "")
    if len(token) < 32:
        raise SystemExit("CC_AGENT_TOKEN is required")
    try:
        client = AgentClient(args.url, token)
        if args.loop:
            try:
                print(json.dumps(run_forever(client, args.agent_id, args.storage_root.resolve(),
                                              poll_interval=args.poll_interval)))
            except KeyboardInterrupt:
                print(json.dumps({"status": "stopped"}))
        else:
            print(json.dumps(run_once(client, args.agent_id, args.storage_root.resolve())))
    except Exception:
        raise SystemExit("Agent run could not complete; no credential or raw error printed")


if __name__ == "__main__":
    main()
