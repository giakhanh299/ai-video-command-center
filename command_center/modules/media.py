import json

from ..errors import DomainError
from ..registry import MODULE_VERSION
from ..storage import inspect_video


def run(config, source, directory, abort):
    if abort.is_set():
        raise DomainError("CANCEL_REQUIRES_RECONCILIATION")
    result = directory / "probe.json"
    with result.open("x", encoding="utf-8") as f:
        json.dump({"schema_version": MODULE_VERSION, "media": inspect_video(source)}, f)
    return [(result, "report", "application/json")]
