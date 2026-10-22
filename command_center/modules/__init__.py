"""Allowlisted task adapters; imports never start bots, queues or models."""
from .media import run as probe
from .basic_render import run as basic_render
from ..errors import DomainError

EXECUTORS = {"media.probe": probe, "render.basic": basic_render}


def execute(module, config, source, directory, abort):
    handler = EXECUTORS.get(module)
    if handler is None:
        raise DomainError("MODULE_NOT_READY")
    directory.mkdir(parents=True, exist_ok=True)
    return handler(config, source, directory, abort)
