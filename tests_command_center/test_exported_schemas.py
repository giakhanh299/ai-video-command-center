import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from command_center.models import CreateJob
from command_center.registry import make_manifest

ROOT = Path(__file__).resolve().parents[1]


def validator(name):
    schema = json.loads((ROOT / "docs/schemas" / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_exported_schemas_accept_real_create_and_manifest():
    request = {"schema_version": "0.1.0-draft", "project_id": str(uuid4()), "preset_id": "basic_render",
               "preset_version": "1.0.0", "input_refs": [str(uuid4())], "overrides": {}}
    validator("create-job.schema.json").validate(request)
    manifest = make_manifest(CreateJob.model_validate(request), uuid4(), datetime.now(timezone.utc))
    validator("manifest.schema.json").validate(manifest)
    manifest["pipeline"][1]["config"]["command"] = "arbitrary"
    with pytest.raises(ValidationError):
        validator("manifest.schema.json").validate(manifest)


def test_openapi_describes_auth_and_typed_job_claim_responses():
    spec = json.loads((ROOT / "docs/openapi.command-center.json").read_text(encoding="utf-8"))
    assert spec["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    for path, method, status in (("/api/v1/jobs", "post", "201"), ("/api/v1/agent/claims", "post", "200")):
        assert "$ref" in spec["paths"][path][method]["responses"][status]["content"]["application/json"]["schema"]
    error = spec["paths"]["/api/v1/jobs"]["post"]["responses"]["422"]["content"]["application/json"]["schema"]
    assert error["$ref"].endswith("/ErrorEnvelope")
    assert "206" in spec["paths"]["/api/v1/files/{fid}/content"]["get"]["responses"]
