from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

VERSION = "0.1.0-draft"
JOB_STATES = ("queued", "running", "cancelling", "needs_review", "needs_attention", "failed", "cancelled")
TASK_STATES = ("queued", "leased", "running", "succeeded", "failed", "cancelled", "needs_attention")
PositiveVersion = Annotated[StrictInt, Field(ge=1)]


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NewProject(Closed):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def printable(cls, value):
        if any(ord(c) < 32 for c in value):
            raise ValueError("Control characters are not allowed")
        return value


class ExpectedVersion(Closed):
    expected_version: PositiveVersion


class EditProject(NewProject, ExpectedVersion):
    pass


class Overrides(Closed):
    title: str = Field(default="", max_length=200)
    width: Literal[360, 720, 1080] | None = None
    height: Literal[640, 1280, 1920] | None = None


class CreateJob(Closed):
    schema_version: Literal["0.1.0-draft"]
    project_id: UUID
    preset_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    preset_version: str = Field(min_length=1, max_length=64)
    input_refs: list[UUID] = Field(min_length=1, max_length=8)
    overrides: Overrides

    @field_validator("input_refs")
    @classmethod
    def distinct(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Duplicate reference")
        return value


class Task(Closed):
    task_id: UUID
    task_key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    module: str
    action: Literal["run"]
    module_version: str
    depends_on: list[UUID] = Field(max_length=32)
    config: dict
    input_refs: list[UUID] = Field(max_length=32)
    output_refs: list[UUID] = Field(max_length=32)
    status: Literal["queued", "leased", "running", "succeeded", "failed", "cancelled", "needs_attention"]
    attempt: Annotated[StrictInt, Field(ge=0)]


class Manifest(Closed):
    schema_version: Literal["0.1.0-draft"]
    project_id: UUID
    job_id: UUID
    created_at: str
    pipeline: list[Task] = Field(min_length=1, max_length=32)
    input_refs: list[UUID] = Field(min_length=1, max_length=8)
    output_refs: list[UUID] = Field(max_length=1024)


class Heartbeat(Closed):
    agent_id: UUID
    capability_version: str = Field(min_length=1, max_length=64)
    active_attempt_ids: list[UUID] = Field(max_length=16)


class ClaimRequest(Closed):
    agent_id: UUID
    resource: Literal["cpu:0", "gpu:0"]


class Lease(Closed):
    attempt: Annotated[StrictInt, Field(ge=1)]
    lease_token: UUID


class TaskEvent(Lease):
    event_id: UUID
    level: Literal["info", "warning", "error"]
    code: Literal["TASK_STARTED", "TASK_PROGRESS", "TASK_WARNING", "TASK_FAILED"]
    message: str = Field(max_length=500)


class Complete(Lease):
    status: Literal["succeeded", "failed", "needs_attention", "cancelled"]
    output_ids: list[UUID] = Field(max_length=32)
    error_code: Literal["EXECUTION_FAILED", "INPUT_CHANGED", "MODULE_NOT_READY", "CANCEL_REQUIRES_RECONCILIATION"] | None = None
    stop_receipt_id: UUID | None = None

    @field_validator("output_ids")
    @classmethod
    def distinct(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Duplicate output")
        return value


class FileRegistration(Lease):
    project_id: UUID
    job_id: UUID
    task_id: UUID
    logical_name: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    kind: Literal["video", "audio", "subtitle", "report", "packet"]
    media_type: Literal["video/mp4", "audio/wav", "application/json", "application/x-subrip"]
    size_bytes: Annotated[StrictInt, Field(gt=0, le=524288000)]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    storage_key: str = Field(min_length=1, max_length=240)


class ErrorInfo(Closed):
    code: str
    message: str


class ErrorBody(ErrorInfo):
    request_id: str
    details: list[dict]


class ErrorEnvelope(Closed):
    error: ErrorBody


class ProjectDTO(Closed):
    id: UUID
    name: str
    version: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskDTO(Closed):
    id: UUID
    task_key: str
    module: str
    action: Literal["run"]
    module_version: str
    status: Literal["queued", "leased", "running", "succeeded", "failed", "cancelled", "needs_attention"]
    attempt: int
    depends_on: list[UUID]
    error: ErrorInfo | None


class Progress(Closed):
    completed_tasks: int
    total_tasks: int
    percent: float | None


class JobDTO(Closed):
    id: UUID
    project_id: UUID
    preset_id: str
    preset_version: str
    status: Literal["queued", "running", "cancelling", "needs_review", "needs_attention", "failed", "cancelled"]
    version: int
    created_at: datetime
    updated_at: datetime
    progress: Progress
    current_task_id: UUID | None
    error: ErrorInfo | None
    tasks: list[TaskDTO]


class EventDTO(Closed):
    id: UUID
    sequence: int
    job_id: UUID
    task_id: UUID | None
    timestamp: datetime
    level: Literal["info", "warning", "error"]
    code: str
    message: str


class FileDTO(Closed):
    id: UUID
    kind: Literal["video", "audio", "subtitle", "report", "packet"]
    media_type: str
    size_bytes: int
    sha256: str
    verification: Literal["pending", "verified", "rejected"]
    playback_url: str | None
    expires_at: datetime | None


class AgentDTO(Closed):
    id: UUID
    status: Literal["online", "offline", "disabled"]
    last_seen_at: datetime | None
    capabilities: list[str]
    active_task_count: int


T = TypeVar("T")


class Page(Closed, Generic[T]):
    items: list[T]
    next_cursor: str | None


class Items(Closed, Generic[T]):
    items: list[T]


class FileBinding(Closed):
    id: UUID
    storage_key: str
    kind: str
    media_type: str
    size_bytes: int
    sha256: str


class ClaimDTO(Closed):
    task: TaskDTO
    manifest: Manifest
    attempt: int
    attempt_id: UUID
    lease_token: UUID
    lease_expires_at: datetime
    input_files: list[FileBinding]


class RenewDTO(Closed):
    lease_expires_at: datetime
    cancel_requested: bool


class HeartbeatDTO(Closed):
    server_time: datetime
    lease_seconds: int
