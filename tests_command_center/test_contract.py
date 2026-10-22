import copy
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from command_center.errors import DomainError
from command_center.models import CreateJob
from command_center.registry import make_manifest, validate_manifest
from command_center.storage import storage_path


def request():
    return {"schema_version": "0.1.0-draft", "project_id": str(uuid4()), "preset_id": "basic_render",
            "preset_version": "1.0.0", "input_refs": [str(uuid4())], "overrides": {}}


@pytest.mark.parametrize("field,value", [("command", "powershell"), ("attempt", 8), ("status", "succeeded"), ("channel_cfg", {"token": "private"})])
def test_reject_client_owned_execution_fields(field, value):
    body = request()
    body[field] = value
    with pytest.raises(ValidationError):
        CreateJob.model_validate(body)


@pytest.mark.parametrize("mutation", ["cycle", "unknown_module", "extra_config", "duplicate_task", "missing_dependency", "unbound_file", "wrong_version"])
def test_agent_rejects_invalid_manifest(mutation):
    value = make_manifest(CreateJob.model_validate(request()), uuid4(), datetime.now(timezone.utc))
    if mutation == "cycle":
        value["pipeline"][0]["depends_on"] = [value["pipeline"][1]["task_id"]]
    elif mutation == "unknown_module":
        value["pipeline"][0]["module"] = "os.system"
    elif mutation == "extra_config":
        value["pipeline"][0]["config"]["shell"] = "echo arbitrary"
    elif mutation == "duplicate_task":
        value["pipeline"][1]["task_id"] = value["pipeline"][0]["task_id"]
    elif mutation == "missing_dependency":
        value["pipeline"][1]["depends_on"] = [str(uuid4())]
    elif mutation == "unbound_file":
        value["pipeline"][0]["input_refs"] = [str(uuid4())]
    else:
        value["pipeline"][0]["module_version"] = "uninstalled"
    with pytest.raises(DomainError, match="INVALID_MANIFEST"):
        validate_manifest(value)


@pytest.mark.parametrize("key", ["../escape.mp4", "C:/escape.mp4", "/absolute", "a\\b.mp4", "a//b.mp4", "a/./b.mp4"])
def test_storage_escape_rejected(tmp_path, key):
    with pytest.raises(DomainError):
        storage_path(tmp_path, key)


def test_pilot_does_not_silently_ignore_title_override():
    body = request()
    body["overrides"] = {"title": "Tiêu đề phải được xử lý hoặc từ chối"}
    with pytest.raises(DomainError, match="OVERRIDE_NOT_SUPPORTED"):
        make_manifest(CreateJob.model_validate(body), uuid4(), datetime.now(timezone.utc))
