"""Local HTTP + outbound Agent smoke on synthetic media. Prints no credentials."""
import json
import pathlib
import subprocess
import sys
from uuid import UUID, uuid4

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from command_center.agent import AgentClient, run_once
from command_center.cli import import_input
from command_center.settings import Settings


def main():
    config = json.loads((ROOT / "workspace/command_center_dev/credentials.local.json").read_text())
    settings = Settings(database_url=config["database_url"], owner_token=config["owner_token"],
                        owner_id=UUID(config["owner_id"]), storage_root=pathlib.Path(config["storage_root"]))
    client = httpx.Client(base_url="http://127.0.0.1:8016", headers={"Authorization": "Bearer " + settings.owner_token}, timeout=30, trust_env=False)
    assert client.get("/api/v1/ready").status_code == 200
    run_id = uuid4().hex
    work = ROOT / "workspace/command_center_dev/smoke" / run_id
    work.mkdir(parents=True)
    source = work / "source.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x480:rate=24:duration=1",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(source)], check=True, timeout=30)
    p = client.post("/api/v1/projects", headers={"Idempotency-Key": "smoke-project-" + run_id}, json={"name": "Kiểm thử HTTP render CPU " + run_id[:8]})
    p.raise_for_status()
    pid = p.json()["id"]
    fid = import_input(settings, UUID(pid), source)
    job = client.post("/api/v1/jobs", headers={"Idempotency-Key": "smoke-job-" + run_id}, json={
        "schema_version": "0.1.0-draft", "project_id": pid, "preset_id": "basic_render", "preset_version": "1.0.0",
        "input_refs": [str(fid)], "overrides": {}})
    job.raise_for_status()
    jid = job.json()["id"]
    agent = AgentClient("http://127.0.0.1:8016", config["agent_token"])
    states = [run_once(agent, UUID(config["agent_id"]), settings.storage_root) for _ in range(2)]
    assert all(v["status"] == "succeeded" for v in states)
    final = client.get("/api/v1/jobs/" + jid).json()
    assert final["status"] == "needs_review"
    outputs = client.get(f"/api/v1/jobs/{jid}/outputs").json()["items"]
    video = next(o for o in outputs if o["kind"] == "video")
    content = client.get(f"/api/v1/files/{video['id']}/content", headers={"Range": "bytes=0-127"})
    assert content.status_code == 206 and len(content.content) == 128
    from command_center.db import Database
    from command_center.storage import storage_path, inspect_video
    with Database(settings.database_url).connect() as c:
        row = c.execute("SELECT storage_key FROM command_center.files WHERE id=%s", (video["id"],)).fetchone()
    media = inspect_video(storage_path(settings.storage_root, row["storage_key"]))
    summary = {"mode": "real-local-http", "synthetic_media": True, "database": "PostgreSQL Docker",
               "project_id": pid, "job_id": jid, "job_status": final["status"], "agent_tasks": states,
               "video_file_id": video["id"], "media": media, "range_http": content.status_code,
               "output_count": len(outputs), "tts_tested": False, "wuby_tested": False, "cloud_upload_tested": False}
    (ROOT / "workspace/command_center_dev/smoke-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Smoke failed; no credentials or raw HTTP/driver error printed")
        raise SystemExit(1)
