from __future__ import annotations

import hashlib
import hmac
from uuid import UUID, uuid4

import psycopg
from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import Database
from .errors import DomainError
from .models import (VERSION, NewProject, EditProject, ExpectedVersion, CreateJob, Heartbeat,
                     ClaimRequest, Lease, TaskEvent, Complete, FileRegistration, ProjectDTO,
                     JobDTO, TaskDTO, EventDTO, FileDTO, AgentDTO, Page, Items, ClaimDTO, RenewDTO, HeartbeatDTO, ErrorEnvelope)
from .registry import module_dtos, preset_dtos
from .repository import Repository
from .settings import Settings
from .storage import verify_file

bearer = HTTPBearer(auto_error=False)


def create_app(settings: Settings | None = None):
    settings = settings or Settings.load()
    db = Database(settings.database_url)
    repo = Repository(db, settings)
    app = FastAPI(title="AI Video Command Center", version=VERSION,
                  responses={status: {"model": ErrorEnvelope} for status in (401, 403, 404, 409, 413, 422, 429, 500, 503)})
    app.state.repository = repo

    def failure(request, code, status, details=None):
        return JSONResponse(status_code=status, content={"error": {"code": code,
            "message": "Yêu cầu không thể thực hiện. Kiểm tra mã lỗi và trạng thái hệ thống.",
            "request_id": getattr(request.state, "request_id", uuid4().hex), "details": details or []}})

    @app.middleware("http")
    async def bounds(request: Request, call_next):
        request.state.request_id = uuid4().hex
        # Read through the bounded stream: handles both Content-Length and chunked bodies.
        if request.method in ("POST", "PATCH", "PUT", "DELETE"):
            max_bytes = 100 * 1024 * 1024 if request.url.path.endswith("/upload") else 256 * 1024
            chunks, count = [], 0
            async for part in request.stream():
                count += len(part)
                if count > max_bytes:
                    return failure(request, "REQUEST_TOO_LARGE", 413)
                chunks.append(part)
            request._body = b"".join(chunks)
        try:
            response = await call_next(request)
        except Exception:
            # Do not let an unexpected exception print a DSN/raw payload in server logs.
            response = failure(request, "INTERNAL_ERROR", 500)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return failure(request, exc.code, exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic's default response includes raw input; never return credentials/config blobs.
        return failure(request, "VALIDATION_ERROR", 422)

    @app.exception_handler(psycopg.Error)
    async def database_error(request, exc):
        return failure(request, "DATABASE_UNAVAILABLE", 503)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return failure(request, "INTERNAL_ERROR", 500)

    def owner(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if len(settings.owner_token) < 32:
            raise DomainError("AUTH_NOT_CONFIGURED", 503)
        if not credentials or credentials.scheme.lower() != "bearer" or not hmac.compare_digest(
            hashlib.sha256(credentials.credentials.encode()).digest(), hashlib.sha256(settings.owner_token.encode()).digest()
        ):
            raise DomainError("UNAUTHORIZED", 401)
        return settings.owner_id

    def agent(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if not credentials or credentials.scheme.lower() != "bearer":
            raise DomainError("UNAUTHORIZED", 401)
        return repo.agent_by_token(credentials.credentials)

    def key(request: Request):
        value = request.headers.get("Idempotency-Key", "")
        if not 8 <= len(value) <= 128 or not value.isascii() or not value.isprintable():
            raise DomainError("IDEMPOTENCY_KEY_REQUIRED", 422)
        return value

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "api_version": VERSION}

    @app.get("/api/v1/ready")
    def ready(principal=Depends(owner)):
        db.ready()
        return {"status": "ready", "database": "ready"}

    @app.get("/api/v1/modules")
    def modules(principal=Depends(owner)):
        return {"items": module_dtos()}

    @app.get("/api/v1/presets")
    def presets(principal=Depends(owner)):
        return {"items": preset_dtos()}

    @app.get("/api/v1/projects", response_model=Page[ProjectDTO])
    def projects(cursor: str | None = None, limit: int = Query(25, ge=1, le=100), principal=Depends(owner)):
        return repo.projects(principal, cursor, limit)

    @app.post("/api/v1/projects", status_code=201, response_model=ProjectDTO)
    def new_project(body: NewProject, principal=Depends(owner), idempotency=Depends(key)):
        return repo.create_project(principal, body.name, idempotency)

    @app.get("/api/v1/projects/{pid}", response_model=ProjectDTO)
    def get_project(pid: UUID, principal=Depends(owner)):
        return repo.get_project(principal, pid)

    @app.patch("/api/v1/projects/{pid}", response_model=ProjectDTO)
    def edit_project(pid: UUID, body: EditProject, principal=Depends(owner)):
        return repo.edit_project(principal, pid, body.expected_version, body.name)

    @app.delete("/api/v1/projects/{pid}", response_model=ProjectDTO)
    def archive_project(pid: UUID, body: ExpectedVersion, principal=Depends(owner)):
        return repo.edit_project(principal, pid, body.expected_version, archive=True)

    @app.post("/api/v1/jobs", status_code=201, response_model=JobDTO)
    def create_job(body: CreateJob, principal=Depends(owner), idempotency=Depends(key)):
        return repo.create_job(principal, body, idempotency)

    @app.get("/api/v1/jobs", response_model=Page[JobDTO])
    def all_jobs(cursor: str | None = None, limit: int = Query(25, ge=1, le=100), status: str | None = None, principal=Depends(owner)):
        return repo.all_jobs(principal, cursor, limit, status)

    @app.get("/api/v1/projects/{pid}/jobs", response_model=Page[JobDTO])
    def jobs(pid: UUID, cursor: str | None = None, limit: int = Query(25, ge=1, le=100), status: str | None = None, principal=Depends(owner)):
        return repo.jobs(principal, pid, cursor, limit, status)

    @app.get("/api/v1/projects/{pid}/files", response_model=Items[FileDTO])
    def project_files(pid: UUID, principal=Depends(owner)):
        return repo.project_files(principal, pid)

    @app.post("/api/v1/projects/{pid}/upload", status_code=201, response_model=FileDTO)
    async def upload_project_file(pid: UUID, request: Request, principal=Depends(owner)):
        raw = await request.body()
        fname = request.headers.get("X-File-Name", "upload.mp4")
        return repo.upload_project_file(principal, pid, fname, raw)

    @app.post("/api/v1/projects/{pid}/ingest-source")
    async def ingest_source(pid: UUID, request: Request, principal=Depends(owner)):
        body = await request.json()
        return repo.ingest_source_url(principal, pid, body.get("source_input", ""))

    @app.get("/api/v1/jobs/{jid}", response_model=JobDTO)
    def job(jid: UUID, principal=Depends(owner)):
        return repo.get_job(principal, jid)

    @app.post("/api/v1/jobs/{jid}/cancel", status_code=202, response_model=JobDTO)
    def cancel(jid: UUID, body: ExpectedVersion, response: Response, principal=Depends(owner)):
        result, replayed = repo.cancel(principal, jid, body.expected_version)
        if replayed:
            response.status_code = 200
        return result

    @app.post("/api/v1/jobs/{jid}/retry", status_code=202, response_model=JobDTO)
    def retry(jid: UUID, body: ExpectedVersion, principal=Depends(owner), idempotency=Depends(key)):
        return repo.retry(principal, jid, body.expected_version, idempotency)

    @app.get("/api/v1/jobs/{jid}/events", response_model=Page[EventDTO])
    def events(jid: UUID, cursor: str | None = None, limit: int = Query(25, ge=1, le=100), principal=Depends(owner)):
        return repo.events(principal, jid, cursor, limit)

    @app.get("/api/v1/jobs/{jid}/outputs", response_model=Items[FileDTO])
    def outputs(jid: UUID, principal=Depends(owner)):
        return repo.outputs(principal, jid)

    @app.get("/api/v1/files/{fid}/content", response_class=FileResponse, responses={
        200: {"description": "Verified local video or JSON report", "content": {
            "video/mp4": {"schema": {"type": "string", "format": "binary"}},
            "application/json": {"schema": {"type": "object"}}}},
        206: {"description": "Partial verified content for a valid Range request", "content": {
            "video/mp4": {"schema": {"type": "string", "format": "binary"}}}},
    })
    def file_content(fid: UUID, principal=Depends(owner)):
        with db.connect() as c:
            f = c.execute("SELECT f.* FROM command_center.files f JOIN command_center.projects p ON p.id=f.project_id WHERE f.id=%s AND p.owner_id=%s AND f.verification='verified'", (fid, principal)).fetchone()
            if not f:
                raise DomainError("NOT_FOUND", 404)
            path = verify_file(settings.storage_root, f)
            return FileResponse(path, media_type=f["media_type"], filename=f["logical_name"], content_disposition_type="inline")

    @app.get("/api/v1/agents", response_model=Page[AgentDTO])
    def agents(cursor: str | None = None, limit: int = Query(25, ge=1, le=100), principal=Depends(owner)):
        return repo.agents(principal, cursor, limit)

    @app.post("/api/v1/agent/heartbeat", response_model=HeartbeatDTO)
    def heartbeat(body: Heartbeat, principal=Depends(agent)):
        return repo.heartbeat(principal, body)

    @app.post("/api/v1/agent/claims", response_model=ClaimDTO, responses={204: {"description": "No eligible task"}})
    def claim(body: ClaimRequest, principal=Depends(agent)):
        result = repo.claim(principal, body)
        return result if result else Response(status_code=204)

    @app.post("/api/v1/agent/tasks/{tid}/renew", response_model=RenewDTO)
    def renew(tid: UUID, body: Lease, principal=Depends(agent)):
        return repo.renew(principal, tid, body)

    @app.post("/api/v1/agent/tasks/{tid}/events", status_code=201, response_model=EventDTO)
    def task_event(tid: UUID, body: TaskEvent, response: Response, principal=Depends(agent)):
        result, replayed = repo.task_event(principal, tid, body)
        if replayed:
            response.status_code = 200
        return result

    @app.post("/api/v1/agent/files", status_code=201, response_model=FileDTO)
    def register_file(body: FileRegistration, principal=Depends(agent)):
        return repo.register_file(principal, body)

    @app.post("/api/v1/agent/tasks/{tid}/complete", response_model=TaskDTO)
    def complete(tid: UUID, body: Complete, principal=Depends(agent)):
        return repo.complete(principal, tid, body)

    return app


app = create_app()
