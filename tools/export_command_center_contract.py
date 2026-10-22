"""Export public API/schema files. No environment credentials or DB access required."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from command_center.api import create_app
from command_center.models import CreateJob, Manifest
from command_center.registry import MODULES, MODULE_VERSION, module_dtos, preset_dtos
from command_center.settings import Settings


def main():
    docs = ROOT / "docs"
    schemas = docs / "schemas"
    schemas.mkdir(exist_ok=True)
    manifest = Manifest.model_json_schema()
    manifest["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    manifest["properties"]["created_at"]["format"] = "date-time"
    task = manifest["$defs"]["Task"]
    task["properties"]["module"]["enum"] = [k for k, v in MODULES.items() if v["available"]]
    task["properties"]["module_version"]["const"] = MODULE_VERSION
    task["allOf"] = [{"if": {"properties": {"module": {"const": name}}, "required": ["module"]},
                       "then": {"properties": {"config": value["config_schema"]}}}
                      for name, value in MODULES.items() if value["available"]]
    for field in ("input_refs", "output_refs"):
        manifest["properties"][field]["uniqueItems"] = True
        task["properties"][field]["uniqueItems"] = True
    task["properties"]["depends_on"]["uniqueItems"] = True
    create = CreateJob.model_json_schema()
    create["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    create["properties"]["input_refs"]["uniqueItems"] = True
    outputs = {
        docs / "openapi.command-center.json": create_app(Settings()).openapi(),
        schemas / "create-job.schema.json": create,
        schemas / "manifest.schema.json": manifest,
        schemas / "registry.json": {"modules": module_dtos(), "presets": preset_dtos()},
    }
    for path, value in outputs.items():
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Exported OpenAPI, CreateJob/Manifest schemas, public registry")


if __name__ == "__main__":
    main()
