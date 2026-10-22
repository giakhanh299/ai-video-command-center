"""Explicit registry. Nothing in JSON is imported or executed as a command."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker

from .errors import DomainError
from .models import CreateJob, Manifest, VERSION

MODULE_VERSION = "1.0.0"
EMPTY_CONFIG = {"type": "object", "properties": {}, "additionalProperties": False}
BASIC_CONFIG = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "width": {"type": "integer", "enum": [360, 720, 1080]},
        "height": {"type": "integer", "enum": [640, 1280, 1920]},
    }, "required": ["width", "height"],
}
MODULES = {
    "media.probe": {"config_schema": EMPTY_CONFIG, "resource": "cpu:0", "available": True},
    "render.basic": {"config_schema": BASIC_CONFIG, "resource": "cpu:0", "available": True},
    "render.compose": {"config_schema": EMPTY_CONFIG, "resource": "gpu:0", "available": False},
    "render.rerender": {"config_schema": EMPTY_CONFIG, "resource": "gpu:0", "available": False},
}
PRESETS = {
    "inspect_media": {"label": "Kiểm tra thông số video", "modules": ["media.probe"], "available": True},
    "basic_render": {"label": "Render cơ bản CPU — giữ âm thanh gốc", "modules": ["media.probe", "render.basic"], "available": True},
    "wuby": {"label": "Wuby — đang tích hợp adapter", "modules": ["render.compose"], "available": False},
    "cauhinh2": {"label": "Film review black — đang tích hợp", "modules": ["render.compose"], "available": False},
    "cauhinh3": {"label": "Movie clone — đang tích hợp", "modules": ["render.compose"], "available": False},
    "cauhinh3_wuby": {"label": "Wuby AI giữ nền — đang tích hợp", "modules": ["render.compose"], "available": False},
    "chidepdicau": {"label": "Chị đẹp đi câu — đang tích hợp", "modules": ["render.compose"], "available": False},
    "song1minhcogivui": {"label": "Sống một mình — đang tích hợp", "modules": ["render.compose"], "available": False},
}


def validate_manifest(data: dict) -> Manifest:
    try:
        manifest = Manifest.model_validate(data)
        created = datetime.fromisoformat(manifest.created_at.replace("Z", "+00:00"))
        if created.tzinfo is None or created.utcoffset() is None:
            raise ValueError("Timezone required")
        if len(set(manifest.input_refs)) != len(manifest.input_refs):
            raise ValueError("Duplicate input")
        ids = {t.task_id for t in manifest.pipeline}
        if len(ids) != len(manifest.pipeline) or len({t.task_key for t in manifest.pipeline}) != len(ids):
            raise ValueError("Duplicate task")
        graph = {}
        for task in manifest.pipeline:
            module = MODULES.get(task.module)
            if not module or not module["available"] or task.module_version != MODULE_VERSION:
                raise ValueError("Unregistered module")
            Draft202012Validator(module["config_schema"]).validate(task.config)
            if len(set(task.depends_on)) != len(task.depends_on) or not set(task.depends_on) <= ids:
                raise ValueError("Invalid dependency")
            if not set(task.input_refs) <= set(manifest.input_refs):
                raise ValueError("Unbound input")
            if len(set(task.input_refs)) != len(task.input_refs) or len(set(task.output_refs)) != len(task.output_refs):
                raise ValueError("Duplicate reference")
            graph[task.task_id] = task.depends_on
        done, visiting = set(), set()

        def visit(node):
            if node in visiting:
                raise ValueError("Cycle")
            if node in done:
                return
            visiting.add(node)
            for dep in graph[node]:
                visit(dep)
            visiting.remove(node)
            done.add(node)

        for node in graph:
            visit(node)
        return manifest
    except Exception as exc:
        raise DomainError("INVALID_MANIFEST", 422) from exc


def make_manifest(request: CreateJob, job_id, created_at):
    preset = PRESETS.get(request.preset_id)
    if not preset or request.preset_version != MODULE_VERSION:
        raise DomainError("INVALID_PRESET", 422)
    if not preset["available"]:
        raise DomainError("MODULE_NOT_READY")
    if len(request.input_refs) != 1:
        raise DomainError("SINGLE_VIDEO_REQUIRED", 422)
    if request.overrides.title:
        raise DomainError("OVERRIDE_NOT_SUPPORTED", 422)
    if request.preset_id != "basic_render" and (request.overrides.width is not None or request.overrides.height is not None):
        raise DomainError("OVERRIDE_NOT_SUPPORTED", 422)
    width = request.overrides.width or 720
    height = request.overrides.height or 1280
    tasks = []
    for index, module in enumerate(preset["modules"]):
        task_id = uuid4()
        tasks.append({
            "task_id": str(task_id), "task_key": "probe" if index == 0 else "compose",
            "module": module, "action": "run", "module_version": MODULE_VERSION,
            "depends_on": [tasks[-1]["task_id"]] if tasks else [],
            "config": {"width": width, "height": height} if module == "render.basic" else {},
            "input_refs": [str(v) for v in request.input_refs], "output_refs": [],
            "status": "queued", "attempt": 0,
        })
    value = {"schema_version": VERSION, "project_id": str(request.project_id), "job_id": str(job_id),
             "created_at": created_at.isoformat(), "pipeline": tasks,
             "input_refs": [str(v) for v in request.input_refs], "output_refs": []}
    return validate_manifest(value).model_dump(mode="json")


def module_dtos():
    return [{"id": k, "version": MODULE_VERSION, "actions": ["run"], "resource": v["resource"],
             "config_schema": v["config_schema"], "available": v["available"],
             "unavailable_reason": None if v["available"] else "ADAPTER_NOT_INTEGRATED"}
            for k, v in MODULES.items()]


def preset_dtos():
    return [{"id": k, "version": MODULE_VERSION, "label": v["label"], "available": v["available"],
             "modules": v["modules"],
             "override_schema": (BASIC_CONFIG if k == "basic_render" else EMPTY_CONFIG) if v["available"] else CreateJob.model_json_schema()["$defs"]["Overrides"]}
            for k, v in PRESETS.items()]
