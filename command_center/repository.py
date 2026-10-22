from __future__ import annotations

import base64
import hashlib
import json
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from .errors import DomainError
from .models import JOB_STATES
from .registry import MODULES, MODULE_VERSION, make_manifest, validate_manifest
from .storage import verify_file, inspect_video


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False).encode()).hexdigest()


def cursor(value, numeric=False):
    if value is None:
        return 0 if numeric else UUID(int=0)
    try:
        raw = base64.urlsafe_b64decode(value.encode()).decode()
        result = int(raw) if numeric else UUID(raw)
        if numeric and result < 0:
            raise ValueError()
        return result
    except Exception as exc:
        raise DomainError("INVALID_CURSOR", 422) from exc


def encode_cursor(value):
    return base64.urlsafe_b64encode(str(value).encode()).decode()


def advisory(c, scope):
    key = int.from_bytes(hashlib.sha256(scope.encode()).digest()[:8], "big", signed=True)
    c.execute("SELECT pg_advisory_xact_lock(%s)", (key,))


def project(c, owner, project_id, lock=False):
    row = c.execute("SELECT * FROM command_center.projects WHERE id=%s AND owner_id=%s" +
                    (" FOR UPDATE" if lock else ""), (project_id, owner)).fetchone()
    if not row:
        raise DomainError("NOT_FOUND", 404)
    return row


def project_dto(row):
    return {k: row[k] for k in ("id", "name", "version", "archived_at", "created_at", "updated_at")}


def task_dto(c, row):
    return {"id": row["id"], "task_key": row["task_key"], "module": row["module"], "action": "run",
            "module_version": row["module_version"], "status": row["status"], "attempt": row["attempt"],
            "depends_on": [r["dependency_id"] for r in c.execute(
                "SELECT dependency_id FROM command_center.task_dependencies WHERE task_id=%s ORDER BY dependency_id", (row["id"],))],
            "error": {"code": row["error_code"], "message": "Bước xử lý cần kiểm tra."} if row["error_code"] else None}


def job_row(c, owner, job_id, lock=False):
    row = c.execute("SELECT j.* FROM command_center.jobs j JOIN command_center.projects p ON p.id=j.project_id "
                    "WHERE j.id=%s AND p.owner_id=%s" + (" FOR UPDATE OF j" if lock else ""), (job_id, owner)).fetchone()
    if not row:
        raise DomainError("NOT_FOUND", 404)
    return row


def job_dto(c, row):
    tasks = c.execute("SELECT * FROM command_center.tasks WHERE job_id=%s ORDER BY task_key", (row["id"],)).fetchall()
    completed = sum(t["status"] == "succeeded" for t in tasks)
    current = next((t["id"] for t in tasks if t["status"] in ("leased", "running")), None)
    result = {k: row[k] for k in ("id", "project_id", "preset_id", "preset_version", "status", "version", "created_at", "updated_at")}
    result.update(progress={"completed_tasks": completed, "total_tasks": len(tasks),
                            "percent": round(100 * completed / len(tasks), 2) if completed and tasks else None},
                  current_task_id=current,
                  error={"code": row["error_code"], "message": "Job cần kiểm tra."} if row["error_code"] else None,
                  tasks=[task_dto(c, t) for t in tasks])
    return result


def event(c, job_id, task_id, code, level="info", event_id=None):
    # Never persist an arbitrary Agent error/message: it can contain paths or secrets.
    text = {"JOB_QUEUED": "Job đã được xếp hàng.", "TASK_CLAIMED": "Agent đã nhận task.",
            "TASK_STARTED": "Task bắt đầu xử lý.", "TASK_SUCCEEDED": "Task hoàn tất.",
            "LEASE_EXPIRED": "Mất lease; cần đối soát tiến trình trước khi thử lại.",
            "JOB_CANCEL_REQUESTED": "Đã yêu cầu dừng job.", "JOB_RETRY": "Job đã được yêu cầu thử lại."}.get(code, "Trạng thái xử lý đã cập nhật.")
    return c.execute("INSERT INTO command_center.events(id,job_id,task_id,level,code,message) VALUES(%s,%s,%s,%s,%s,%s) RETURNING *",
                     (event_id or uuid4(), job_id, task_id, level, code, text)).fetchone()


def replay(c, owner, route, key, body):
    advisory(c, f"idempotency:{owner}:{route}:{key}")
    row = c.execute("SELECT * FROM command_center.idempotency_keys WHERE owner_id=%s AND route=%s AND key=%s",
                    (owner, route, key)).fetchone()
    if row and row["request_digest"] != digest(body):
        raise DomainError("IDEMPOTENCY_CONFLICT")
    return row["resource_id"] if row else None


def remember(c, owner, route, key, body, resource_id):
    c.execute("INSERT INTO command_center.idempotency_keys(owner_id,route,key,request_digest,resource_id) VALUES(%s,%s,%s,%s,%s)",
              (owner, route, key, digest(body), resource_id))


class Repository:
    def __init__(self, database, settings):
        self.db, self.settings = database, settings

    def create_project(self, owner, name, key):
        body = {"name": name}
        with self.db.connect() as c:
            existing = replay(c, owner, "POST /projects", key, body)
            if existing:
                return project_dto(project(c, owner, existing))
            row = c.execute("INSERT INTO command_center.projects(id,owner_id,name) VALUES(%s,%s,%s) RETURNING *", (uuid4(), owner, name)).fetchone()
            remember(c, owner, "POST /projects", key, body, row["id"])
            return project_dto(row)

    def projects(self, owner, token, limit):
        after = cursor(token)
        with self.db.connect() as c:
            rows = c.execute("SELECT * FROM command_center.projects WHERE owner_id=%s AND id>%s ORDER BY id LIMIT %s",
                             (owner, after, limit + 1)).fetchall()
            return {"items": [project_dto(r) for r in rows[:limit]],
                    "next_cursor": encode_cursor(rows[limit - 1]["id"]) if len(rows) > limit else None}

    def get_project(self, owner, pid):
        with self.db.connect() as c:
            return project_dto(project(c, owner, pid))

    def edit_project(self, owner, pid, expected, name=None, archive=False):
        with self.db.connect() as c:
            row = project(c, owner, pid, True)
            if row["version"] != expected:
                raise DomainError("VERSION_CONFLICT")
            if row["archived_at"]:
                raise DomainError("PROJECT_ARCHIVED")
            if archive and c.execute("SELECT 1 FROM command_center.jobs WHERE project_id=%s AND status IN ('queued','running','cancelling','needs_attention')", (pid,)).fetchone():
                raise DomainError("ACTIVE_JOBS")
            row = c.execute("UPDATE command_center.projects SET name=COALESCE(%s,name),archived_at=CASE WHEN %s THEN clock_timestamp() ELSE archived_at END,version=version+1,updated_at=clock_timestamp() WHERE id=%s RETURNING *",
                            (name, archive, pid)).fetchone()
            return project_dto(row)

    def create_job(self, owner, request, key):
        body = request.model_dump(mode="json")
        with self.db.connect() as c:
            existing = replay(c, owner, "POST /jobs", key, body)
            if existing:
                return job_dto(c, job_row(c, owner, existing))
            p = project(c, owner, request.project_id, True)
            if p["archived_at"]:
                raise DomainError("PROJECT_ARCHIVED")
            jid = uuid4()
            now = c.execute("SELECT clock_timestamp() AS value").fetchone()["value"]
            manifest = make_manifest(request, jid, now)
            for fid in request.input_refs:
                f = c.execute("SELECT * FROM command_center.files WHERE id=%s AND project_id=%s AND verification='verified' AND kind='video'", (fid, request.project_id)).fetchone()
                if not f:
                    raise DomainError("INVALID_INPUT_REF", 422)
                verify_file(self.settings.storage_root, f)
            row = c.execute("INSERT INTO command_center.jobs(id,project_id,preset_id,preset_version,manifest,status) VALUES(%s,%s,%s,%s,%s,'queued') RETURNING *",
                            (jid, request.project_id, request.preset_id, request.preset_version, Jsonb(manifest))).fetchone()
            for t in manifest["pipeline"]:
                c.execute("INSERT INTO command_center.tasks(id,job_id,task_key,module,module_version,config,resource,status,input_refs) VALUES(%s,%s,%s,%s,%s,%s,%s,'queued',%s)",
                          (t["task_id"], jid, t["task_key"], t["module"], t["module_version"], Jsonb(t["config"]), MODULES[t["module"]]["resource"], Jsonb(t["input_refs"])))
            for t in manifest["pipeline"]:
                for dep in t["depends_on"]:
                    c.execute("INSERT INTO command_center.task_dependencies VALUES(%s,%s)", (t["task_id"], dep))
            remember(c, owner, "POST /jobs", key, body, jid)
            event(c, jid, None, "JOB_QUEUED")
            return job_dto(c, row)

    def expire(self, owner):
        with self.db.connect() as c:
            jobs = c.execute("SELECT j.id FROM command_center.jobs j JOIN command_center.projects p ON p.id=j.project_id WHERE p.owner_id=%s AND j.status IN ('running','cancelling') AND EXISTS(SELECT 1 FROM command_center.tasks t WHERE t.job_id=j.id AND t.status IN ('leased','running') AND t.lease_expires_at<clock_timestamp()) FOR UPDATE OF j SKIP LOCKED", (owner,)).fetchall()
            for job in jobs:
                rows = c.execute("UPDATE command_center.tasks SET status='needs_attention',error_code='LEASE_EXPIRED' WHERE job_id=%s AND status IN ('leased','running') AND lease_expires_at<clock_timestamp() RETURNING id", (job["id"],)).fetchall()
                if rows:
                    c.execute("UPDATE command_center.jobs SET status='needs_attention',error_code='LEASE_EXPIRED',version=version+1,updated_at=clock_timestamp() WHERE id=%s", (job["id"],))
                    for row in rows:
                        event(c, job["id"], row["id"], "LEASE_EXPIRED", "warning")
            # Resources deliberately remain quarantined; never replay an uncertain process.

    def get_job(self, owner, jid):
        self.expire(owner)
        with self.db.connect() as c:
            return job_dto(c, job_row(c, owner, jid))

    def jobs(self, owner, pid, token, limit, state):
        after = cursor(token)
        if state and state not in JOB_STATES:
            raise DomainError("INVALID_STATUS", 422)
        self.expire(owner)
        with self.db.connect() as c:
            project(c, owner, pid)
            rows = c.execute("SELECT * FROM command_center.jobs WHERE project_id=%s AND id>%s AND (%s::text IS NULL OR status=%s) ORDER BY id LIMIT %s", (pid, after, state, state, limit + 1)).fetchall()
            return {"items": [job_dto(c, r) for r in rows[:limit]], "next_cursor": encode_cursor(rows[limit - 1]["id"]) if len(rows) > limit else None}

    def all_jobs(self, owner, token, limit, state):
        after = cursor(token)
        if state and state not in JOB_STATES:
            raise DomainError("INVALID_STATUS", 422)
        self.expire(owner)
        with self.db.connect() as c:
            rows = c.execute(
                "SELECT j.* FROM command_center.jobs j JOIN command_center.projects p ON p.id=j.project_id "
                "WHERE p.owner_id=%s AND j.id>%s AND (%s::text IS NULL OR j.status=%s) ORDER BY j.id LIMIT %s",
                (owner, after, state, state, limit + 1),
            ).fetchall()
            return {"items": [job_dto(c, r) for r in rows[:limit]], "next_cursor": encode_cursor(rows[limit - 1]["id"]) if len(rows) > limit else None}

    def project_files(self, owner, pid):
        with self.db.connect() as c:
            project(c, owner, pid)
            rows = c.execute(
                "SELECT * FROM command_center.files WHERE project_id=%s AND verification='verified' AND kind='video' ORDER BY (job_id IS NULL) DESC, created_at DESC LIMIT 50",
                (pid,),
            ).fetchall()
            return {"items": [{"id": r["id"], "kind": r["kind"], "media_type": r["media_type"], "size_bytes": r["size_bytes"],
                               "sha256": r["sha256"], "verification": r["verification"], "playback_url": None, "expires_at": None} for r in rows]}

    def upload_project_file(self, owner, pid, logical_name: str, raw_bytes: bytes):
        if not raw_bytes or len(raw_bytes) > 100 * 1024 * 1024:
            raise DomainError("REQUEST_TOO_LARGE", 413)
        safe_name = "".join(ch for ch in (logical_name or "upload.mp4") if ch.isalnum() or ch in ("-", "_", ".")).strip(".") or "upload.mp4"
        if not safe_name.lower().endswith(".mp4"):
            safe_name += ".mp4"
        fid = uuid4()
        rel_key = f"inputs/{fid}.mp4"
        from .storage import storage_path
        dest = storage_path(self.settings.storage_root, rel_key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw_bytes)
        try:
            inspect_video(dest)
        except Exception:
            if dest.exists():
                dest.unlink()
            raise
        sha = hashlib.sha256(raw_bytes).hexdigest()
        with self.db.connect() as c:
            p = project(c, owner, pid, True)
            if p["archived_at"]:
                if dest.exists():
                    dest.unlink()
                raise DomainError("PROJECT_ARCHIVED")
            row = c.execute(
                "INSERT INTO command_center.files(id,project_id,logical_name,kind,media_type,size_bytes,sha256,storage_key,verification) "
                "VALUES(%s,%s,%s,'video','video/mp4',%s,%s,%s,'verified') RETURNING *",
                (fid, pid, safe_name[:120], len(raw_bytes), sha, rel_key),
            ).fetchone()
            return file_dto(row)

    def ingest_source_url(self, owner, pid, source_input: str):
        text = (source_input or "").strip()
        if not text:
            raise DomainError("VALIDATION_ERROR", 422, "Cần nhập link TikTok/Douyin hoặc tên kênh đầu vào.")

        # Bảng định tuyến tự động 8 kênh đầu vào Douyin/TikTok -> 8 Kênh Fanpage Đích
        rules = [
            {
                "keywords": ["faupskhu", "乖巧宝宝", "quby", "wuby", "kenh_006"],
                "channel_id": "ch_wuby_main",
                "channel_name": "Kênh 1: Wuby Thuyết Minh (KENH_006)",
                "source_author": "乖巧宝宝Quby",
                "preset_id": "cauhinh3_wuby",
                "reason": "Khớp chữ ký kênh nguồn 乖巧宝宝Quby (Hoạt hình Wuby/Quby)",
                "blur_box": {"x": 6, "y": 74, "w": 88, "h": 16},
            },
            {
                "keywords": ["ycerrxgn", "k0iifw0y", "女钓手豆豆", "娜小娜爱钓鱼", "钓鱼", "fishing", "cau ca", "câu cá", "kenh_008"],
                "channel_id": "ch_chidepdicau",
                "channel_name": "Kênh 4: Chị Đẹp Đi Câu (KENH_008)",
                "source_author": "女钓手豆豆 / 娜小娜爱钓鱼",
                "preset_id": "chidepdicau",
                "reason": "Khớp kênh nguồn Nữ Cần Thủ Douyin (女钓手豆豆 / 娜小娜爱钓鱼)",
                "blur_box": {"x": 5, "y": 73, "w": 90, "h": 17},
            },
            {
                "keywords": ["uewx30vr", "阿刚速看", "速看", "解说", "review", "kenh_002"],
                "channel_id": "ch_review_black",
                "channel_name": "KENH_002: Review Phim Black (阿刚速看)",
                "source_author": "阿刚速看",
                "preset_id": "cauhinh2",
                "reason": "Khớp kênh nguồn Tóm tắt & Review Phim 阿刚速看 (KENH_002)",
                "blur_box": {"x": 8, "y": 72, "w": 84, "h": 18},
            },
            {
                "keywords": ["n-1fm0rh", "诡诡漫", "kenh_004"],
                "channel_id": "ch_guiguiman",
                "channel_name": "KENH_004: Truyện Kỳ Bí 诡诡漫",
                "source_author": "诡诡漫",
                "preset_id": "cauhinh2",
                "reason": "Khớp kênh nguồn Hoạt hình Kỳ bí 诡诡漫 (KENH_004)",
                "blur_box": {"x": 6, "y": 71, "w": 88, "h": 18},
            },
            {
                "keywords": ["zjf0uyct", "奋斗的希瓜皮", "希瓜皮", "短剧", "movie", "kenh_005"],
                "channel_id": "ch_movie_clone",
                "channel_name": "KENH_005: Vũ Trụ Cày Phim (奋斗的希瓜皮)",
                "source_author": "奋斗的希瓜皮",
                "preset_id": "cauhinh3",
                "reason": "Khớp kênh nguồn Vũ Trụ Cày Phim (奋斗的希瓜皮 - KENH_005)",
                "blur_box": {"x": 6, "y": 70, "w": 88, "h": 18},
            },
            {
                "keywords": ["d3g0decf", "迷人的歪姐", "歪姐", "独居", "chill", "lofi", "kenh_007"],
                "channel_id": "ch_song1minh",
                "channel_name": "KENH_007: Sống Một Mình (迷人的歪姐)",
                "source_author": "迷人的歪姐",
                "preset_id": "song1minhcogivui",
                "reason": "Khớp kênh nguồn Vlog Đời Sống / Chill (迷人的歪姐 - KENH_007)",
                "blur_box": {"x": 10, "y": 75, "w": 80, "h": 14},
            },
        ]

        lower_text = text.lower()
        matched = None
        for r in rules:
            if any(k in lower_text for k in r["keywords"]):
                matched = r
                break
        if not matched:
            matched = {
                "channel_id": "ch_drama_reels" if "tiktok.com" in lower_text else "ch_review_black",
                "channel_name": "Kênh 7: Drama Tổng Tài" if "tiktok.com" in lower_text else "Kênh 2: Review Phim Black",
                "source_author": "TikTok / Douyin Feed",
                "preset_id": "cauhinh2",
                "reason": "Phân loại tự động theo tên miền & định dạng link video dọc",
                "blur_box": {"x": 6, "y": 71, "w": 88, "h": 18},
            }

        # Nếu là URL video trực tiếp, thử tải nhanh bằng yt-dlp / urllib, nếu kênh user profile thì lấy file mẫu đã xác minh của dự án
        file_obj = None
        import re, subprocess
        url_match = re.search(r"https?://[^\s]+", text)
        if url_match:
            url_str = url_match.group(0)
            if any(x in url_str for x in ("/video/", "v.douyin.com", "vt.tiktok.com", "vm.tiktok.com", ".mp4")):
                fid = uuid4()
                rel_key = f"inputs/{fid}.mp4"
                from .storage import storage_path
                dest = storage_path(self.settings.storage_root, rel_key)
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    cmd = ["yt-dlp", "--no-playlist", "-f", "mp4/best[ext=mp4]/best", "--max-filesize", "95M", "-o", str(dest), url_str]
                    subprocess.run(cmd, capture_output=True, timeout=15, check=True)
                    if dest.exists() and dest.stat().st_size > 1024:
                        inspect_video(dest)
                        raw_bytes = dest.read_bytes()
                        sha = hashlib.sha256(raw_bytes).hexdigest()
                        with self.db.connect() as c:
                            project(c, owner, pid, True)
                            row = c.execute(
                                "INSERT INTO command_center.files(id,project_id,logical_name,kind,media_type,size_bytes,sha256,storage_key,verification) "
                                "VALUES(%s,%s,%s,'video','video/mp4',%s,%s,%s,'verified') RETURNING *",
                                (fid, pid, f"tiktok-{str(fid)[:8]}.mp4", len(raw_bytes), sha, rel_key),
                            ).fetchone()
                            file_obj = file_dto(row)
                except Exception:
                    if dest.exists():
                        dest.unlink(missing_ok=True)

        if not file_obj:
            existing = self.project_files(owner, pid).get("items", [])
            if existing:
                file_obj = existing[0]

        return {
            "detected_channel_id": matched["channel_id"],
            "detected_channel_name": matched["channel_name"],
            "detected_preset_id": matched["preset_id"],
            "source_author": matched["source_author"],
            "classification_reason": matched["reason"],
            "recommended_blur_box": matched["blur_box"],
            "file": file_obj,
        }

    def cancel(self, owner, jid, version):
        with self.db.connect() as c:
            row = job_row(c, owner, jid, True)
            if row["status"] in ("cancelled", "cancelling"):
                return job_dto(c, row), True
            if row["version"] != version:
                raise DomainError("VERSION_CONFLICT")
            if row["status"] not in ("queued", "running"):
                raise DomainError("INVALID_TRANSITION")
            active = c.execute("SELECT 1 FROM command_center.tasks WHERE job_id=%s AND status IN ('leased','running')", (jid,)).fetchone()
            state = "cancelling" if active else "cancelled"
            c.execute("UPDATE command_center.tasks SET status='cancelled' WHERE job_id=%s AND status='queued'", (jid,))
            row = c.execute("UPDATE command_center.jobs SET status=%s,cancel_requested=true,version=version+1,updated_at=clock_timestamp() WHERE id=%s RETURNING *", (state, jid)).fetchone()
            event(c, jid, None, "JOB_CANCEL_REQUESTED")
            return job_dto(c, row), False

    def retry(self, owner, jid, version, key):
        body = {"expected_version": version}
        route = f"POST /jobs/{jid}/retry"
        with self.db.connect() as c:
            existing = replay(c, owner, route, key, body)
            if existing:
                return job_dto(c, job_row(c, owner, existing))
            row = job_row(c, owner, jid, True)
            if row["version"] != version:
                raise DomainError("VERSION_CONFLICT")
            if row["status"] not in ("failed", "needs_attention", "cancelled"):
                raise DomainError("INVALID_TRANSITION")
            if c.execute("SELECT 1 FROM command_center.resources r JOIN command_center.tasks t ON t.id=r.task_id WHERE t.job_id=%s", (jid,)).fetchone():
                raise DomainError("RECONCILIATION_REQUIRED")
            if c.execute("SELECT 1 FROM command_center.tasks WHERE job_id=%s AND status<>'succeeded' AND attempt>=%s", (jid, self.settings.max_attempts)).fetchone():
                raise DomainError("RETRY_LIMIT")
            p = project(c, owner, row["project_id"])
            if p["archived_at"]:
                raise DomainError("PROJECT_ARCHIVED")
            for fid in row["manifest"]["input_refs"]:
                f = c.execute("SELECT * FROM command_center.files WHERE id=%s AND project_id=%s AND verification='verified'", (fid, row["project_id"])).fetchone()
                if not f:
                    raise DomainError("INVALID_INPUT_REF", 422)
                verify_file(self.settings.storage_root, f)
            c.execute("UPDATE command_center.tasks SET status='queued',agent_id=NULL,lease_token=NULL,lease_expires_at=NULL,completion_digest=NULL,error_code=NULL WHERE job_id=%s AND status<>'succeeded'", (jid,))
            row = c.execute("UPDATE command_center.jobs SET status='queued',cancel_requested=false,error_code=NULL,version=version+1,updated_at=clock_timestamp() WHERE id=%s RETURNING *", (jid,)).fetchone()
            remember(c, owner, route, key, body, jid)
            event(c, jid, None, "JOB_RETRY")
            return job_dto(c, row)

    def events(self, owner, jid, token, limit):
        after = cursor(token, True)
        with self.db.connect() as c:
            job_row(c, owner, jid)
            rows = c.execute("SELECT * FROM command_center.events WHERE job_id=%s AND sequence>%s ORDER BY sequence LIMIT %s", (jid, after, limit + 1)).fetchall()
            return {"items": rows[:limit], "next_cursor": encode_cursor(rows[limit - 1]["sequence"]) if len(rows) > limit else None}

    def outputs(self, owner, jid):
        with self.db.connect() as c:
            job_row(c, owner, jid)
            rows = c.execute("SELECT f.* FROM command_center.files f JOIN command_center.tasks t ON t.id=f.task_id WHERE f.job_id=%s AND f.attempt=t.attempt AND t.status='succeeded' AND f.verification='verified' ORDER BY f.id", (jid,)).fetchall()
            return {"items": [file_dto(r) for r in rows]}

    def agents(self, owner, token, limit):
        after = cursor(token)
        with self.db.connect() as c:
            rows = c.execute("SELECT a.*,CASE WHEN a.disabled_at IS NOT NULL THEN 'disabled' WHEN a.last_seen_at>clock_timestamp()-interval '45 seconds' THEN 'online' ELSE 'offline' END AS status,(SELECT count(*) FROM command_center.tasks t WHERE t.agent_id=a.id AND t.status IN ('leased','running')) AS active_task_count FROM command_center.agents a WHERE owner_id=%s AND a.id>%s ORDER BY a.id LIMIT %s", (owner, after, limit + 1)).fetchall()
            return {"items": [{k: r[k] for k in ("id", "status", "last_seen_at", "capabilities", "active_task_count")} for r in rows[:limit]],
                    "next_cursor": encode_cursor(rows[limit - 1]["id"]) if len(rows) > limit else None}

    def agent_by_token(self, token):
        with self.db.connect() as c:
            row = c.execute("SELECT * FROM command_center.agents WHERE credential_hash=%s", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
            if not row:
                raise DomainError("UNAUTHORIZED", 401)
            if row["disabled_at"]:
                raise DomainError("AGENT_DISABLED")
            return row

    def heartbeat(self, agent, request):
        if request.agent_id != agent["id"]:
            raise DomainError("AGENT_SCOPE", 403)
        if request.capability_version != agent["capability_version"]:
            raise DomainError("CAPABILITY_VERSION_MISMATCH")
        self.expire(agent["owner_id"])
        with self.db.connect() as c:
            if request.active_attempt_ids:
                known = c.execute("SELECT id FROM command_center.attempts WHERE agent_id=%s AND id=ANY(%s) AND finished_at IS NULL", (agent["id"], request.active_attempt_ids)).fetchall()
                if len(known) != len(request.active_attempt_ids):
                    raise DomainError("ATTEMPT_SCOPE", 403)
            row = c.execute("UPDATE command_center.agents SET last_seen_at=clock_timestamp() WHERE id=%s RETURNING last_seen_at", (agent["id"],)).fetchone()
            return {"server_time": row["last_seen_at"], "lease_seconds": self.settings.lease_seconds}

    def claim(self, agent, request):
        if request.agent_id != agent["id"]:
            raise DomainError("AGENT_SCOPE", 403)
        self.expire(agent["owner_id"])
        with self.db.connect() as c:
            advisory(c, f"machine:{agent['machine_id']}:{request.resource}")
            if c.execute("SELECT 1 FROM command_center.resources WHERE machine_id=%s AND resource=%s", (agent["machine_id"], request.resource)).fetchone():
                raise DomainError("RESOURCE_BUSY")
            capabilities = agent["capabilities"]
            if not capabilities:
                return None
            row = c.execute("SELECT t.id,t.job_id FROM command_center.tasks t JOIN command_center.jobs j ON j.id=t.job_id JOIN command_center.projects p ON p.id=j.project_id WHERE p.owner_id=%s AND p.archived_at IS NULL AND j.status IN ('queued','running') AND j.cancel_requested=false AND t.status='queued' AND t.resource=%s AND (t.module || '@' || t.module_version)=ANY(%s) AND t.attempt<%s AND NOT EXISTS(SELECT 1 FROM command_center.task_dependencies d JOIN command_center.tasks dependency ON dependency.id=d.dependency_id WHERE d.task_id=t.id AND dependency.status<>'succeeded') ORDER BY j.created_at,t.task_key FOR UPDATE OF j SKIP LOCKED LIMIT 1",
                            (agent["owner_id"], request.resource, capabilities, self.settings.max_attempts)).fetchone()
            if not row:
                return None
            task = c.execute("SELECT * FROM command_center.tasks WHERE id=%s FOR UPDATE", (row["id"],)).fetchone()
            token = uuid4()
            task = c.execute("UPDATE command_center.tasks SET status='leased',attempt=attempt+1,agent_id=%s,lease_token=%s,lease_expires_at=clock_timestamp()+%s*interval '1 second',completion_digest=NULL,error_code=NULL WHERE id=%s RETURNING *", (agent["id"], token, self.settings.lease_seconds, task["id"])).fetchone()
            c.execute("INSERT INTO command_center.resources VALUES(%s,%s,%s)", (agent["machine_id"], request.resource, task["id"]))
            attempt_id = uuid4()
            c.execute("INSERT INTO command_center.attempts(id,task_id,number,agent_id,lease_token) VALUES(%s,%s,%s,%s,%s)", (attempt_id, task["id"], task["attempt"], agent["id"], token))
            job = c.execute("UPDATE command_center.jobs SET status='running',version=version+1,updated_at=clock_timestamp() WHERE id=%s RETURNING *", (task["job_id"],)).fetchone()
            manifest = job["manifest"]
            for t in manifest["pipeline"]:
                stored = c.execute("SELECT status,attempt,output_refs FROM command_center.tasks WHERE id=%s", (t["task_id"],)).fetchone()
                t.update(stored)
            manifest["output_refs"] = [fid for t in manifest["pipeline"] for fid in t["output_refs"]]
            validate_manifest(manifest)
            files = c.execute("SELECT id,storage_key,kind,media_type,size_bytes,sha256 FROM command_center.files WHERE project_id=%s AND id=ANY(%s) AND verification='verified'", (job["project_id"], [UUID(v) for v in task["input_refs"]])).fetchall()
            if len(files) != len(task["input_refs"]):
                raise DomainError("INVALID_INPUT_REF", 422)
            event(c, task["job_id"], task["id"], "TASK_CLAIMED")
            return {"task": task_dto(c, task), "manifest": manifest, "attempt": task["attempt"],
                    "attempt_id": attempt_id, "lease_token": token, "lease_expires_at": task["lease_expires_at"], "input_files": files}

    def locked_task(self, c, agent, tid, request, allow_completed=False):
        summary = c.execute("SELECT job_id FROM command_center.tasks WHERE id=%s", (tid,)).fetchone()
        if not summary:
            raise DomainError("NOT_FOUND", 404)
        job = job_row(c, agent["owner_id"], summary["job_id"], True)
        t = c.execute("SELECT *,lease_expires_at>clock_timestamp() AS live FROM command_center.tasks WHERE id=%s FOR UPDATE", (tid,)).fetchone()
        if t["agent_id"] != agent["id"] or t["attempt"] != request.attempt or t["lease_token"] != request.lease_token:
            raise DomainError("STALE_LEASE")
        if allow_completed and t["completion_digest"]:
            return t, job
        if t["status"] not in ("leased", "running") or not t["live"]:
            raise DomainError("STALE_LEASE")
        return t, job

    def renew(self, agent, tid, request):
        with self.db.connect() as c:
            t, job = self.locked_task(c, agent, tid, request)
            row = c.execute("UPDATE command_center.tasks SET lease_expires_at=clock_timestamp()+%s*interval '1 second' WHERE id=%s RETURNING lease_expires_at", (self.settings.lease_seconds, tid)).fetchone()
            return {**row, "cancel_requested": job["cancel_requested"]}

    def task_event(self, agent, tid, request):
        with self.db.connect() as c:
            t, _ = self.locked_task(c, agent, tid, request)
            old = c.execute("SELECT * FROM command_center.events WHERE id=%s", (request.event_id,)).fetchone()
            if old:
                if old["task_id"] != tid or old["code"] != request.code or old["level"] != request.level:
                    raise DomainError("EVENT_CONFLICT")
                return old, True
            if request.code == "TASK_STARTED":
                c.execute("UPDATE command_center.tasks SET status='running' WHERE id=%s", (tid,))
            return event(c, t["job_id"], tid, request.code, request.level, request.event_id), False

    def register_file(self, agent, request):
        with self.db.connect() as c:
            t, job = self.locked_task(c, agent, request.task_id, request)
            if job["id"] != request.job_id or job["project_id"] != request.project_id:
                raise DomainError("FILE_SCOPE", 403)
            expected = f"attempts/{request.task_id}/{request.attempt}/{request.logical_name}"
            if request.storage_key != expected:
                raise DomainError("INVALID_STORAGE_KEY", 422)
            value = request.model_dump(mode="json")
            verify_file(self.settings.storage_root, value)
            old = c.execute("SELECT * FROM command_center.files WHERE storage_key=%s", (expected,)).fetchone()
            if old:
                if any(str(old[k]) != str(value[k]) for k in ("project_id", "job_id", "task_id", "attempt", "logical_name", "sha256", "size_bytes", "kind", "media_type")):
                    raise DomainError("OUTPUT_CONFLICT")
                return file_dto(old)
            row = c.execute("INSERT INTO command_center.files(id,project_id,job_id,task_id,attempt,logical_name,kind,media_type,size_bytes,sha256,storage_key,verification) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'verified') RETURNING *",
                            (uuid4(), request.project_id, request.job_id, request.task_id, request.attempt, request.logical_name, request.kind, request.media_type, request.size_bytes, request.sha256, expected)).fetchone()
            return file_dto(row)

    def complete(self, agent, tid, request):
        value = request.model_dump(mode="json")
        fingerprint = digest(value)
        with self.db.connect() as c:
            t, job = self.locked_task(c, agent, tid, request, True)
            if t["completion_digest"]:
                if t["completion_digest"] != fingerprint:
                    raise DomainError("COMPLETION_CONFLICT")
                return task_dto(c, t)
            if request.status == "cancelled":
                # No remote process proof verifier is installed yet. Fail closed.
                raise DomainError("STOP_NOT_VERIFIED")
            if job["cancel_requested"] and request.status != "needs_attention":
                raise DomainError("CANCEL_REQUIRES_RECONCILIATION")
            if request.status == "succeeded":
                if not request.output_ids or request.error_code:
                    raise DomainError("OUTPUT_UNVERIFIED")
                registered = []
                for fid in request.output_ids:
                    f = c.execute("SELECT * FROM command_center.files WHERE id=%s AND task_id=%s AND attempt=%s AND verification='verified'", (fid, tid, request.attempt)).fetchone()
                    if not f:
                        raise DomainError("OUTPUT_UNVERIFIED")
                    verify_file(self.settings.storage_root, f)
                    registered.append(f)
                self.verify_task_outputs(c, t, registered)
            elif request.output_ids:
                raise DomainError("INVALID_COMPLETION", 422)
            row = c.execute("UPDATE command_center.tasks SET status=%s,output_refs=%s,error_code=%s,completion_digest=%s WHERE id=%s RETURNING *", (request.status, Jsonb([str(v) for v in request.output_ids]), request.error_code, fingerprint, tid)).fetchone()
            c.execute("UPDATE command_center.attempts SET finished_at=clock_timestamp(),outcome=%s WHERE task_id=%s AND number=%s", (request.status, tid, request.attempt))
            if request.status != "needs_attention":
                c.execute("DELETE FROM command_center.resources WHERE task_id=%s", (tid,))
            remaining = c.execute("SELECT status FROM command_center.tasks WHERE job_id=%s", (job["id"],)).fetchall()
            state = "needs_review" if all(v["status"] == "succeeded" for v in remaining) else "running"
            if request.status in ("failed", "needs_attention"):
                state = request.status
            c.execute("UPDATE command_center.jobs SET status=%s,error_code=%s,version=version+1,updated_at=clock_timestamp() WHERE id=%s", (state, request.error_code, job["id"]))
            event(c, job["id"], tid, "TASK_SUCCEEDED" if request.status == "succeeded" else "TASK_FAILED")
            return task_dto(c, row)

    def verify_task_outputs(self, c, task, registered):
        """Technical output verification, not semantic/voice quality approval."""
        import json
        from fractions import Fraction
        expected = {"probe.json"} if task["module"] == "media.probe" else {"render.mp4", "render-report.json"}
        if {f["logical_name"] for f in registered} != expected or len(registered) != len(expected):
            raise DomainError("OUTPUT_UNVERIFIED")
        source = c.execute("SELECT * FROM command_center.files WHERE id=%s AND verification='verified'", (task["input_refs"][0],)).fetchone()
        if not source:
            raise DomainError("INVALID_INPUT_REF", 422)
        source_path = verify_file(self.settings.storage_root, source)
        original = inspect_video(source_path)
        report_row = next((r for r in registered if r["kind"] == "report"), None)
        if not report_row:
            raise DomainError("OUTPUT_UNVERIFIED")
        report = json.loads(verify_file(self.settings.storage_root, report_row).read_text(encoding="utf-8"))
        if report.get("schema_version") != MODULE_VERSION:
            raise DomainError("OUTPUT_UNVERIFIED")
        if task["module"] == "media.probe":
            if report.get("media") != original:
                raise DomainError("OUTPUT_UNVERIFIED")
            return
        video = next((r for r in registered if r["kind"] == "video"), None)
        if not video:
            raise DomainError("OUTPUT_UNVERIFIED")
        rendered = inspect_video(verify_file(self.settings.storage_root, video))
        cfg = task["config"]
        tolerance = 1 / float(Fraction(original["fps"])) + .05
        if (rendered["width"], rendered["height"]) != (cfg["width"], cfg["height"]) or rendered["fps"] != original["fps"] or rendered["has_audio"] != original["has_audio"] or abs(rendered["duration"] - original["duration"]) > tolerance:
            raise DomainError("OUTPUT_UNVERIFIED")
        if original["frames"] is not None and rendered["frames"] != original["frames"]:
            raise DomainError("OUTPUT_UNVERIFIED")
        if report.get("media") != rendered or report.get("source_sha256") != source["sha256"] or report.get("output_sha256") != video["sha256"]:
            raise DomainError("OUTPUT_UNVERIFIED")


def file_dto(row):
    return {**{k: row[k] for k in ("id", "kind", "media_type", "size_bytes", "sha256", "verification")},
            "playback_url": None, "expires_at": None}
