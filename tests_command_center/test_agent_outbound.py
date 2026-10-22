"""Outbound-443 Agent rules: URL enforcement and the wait-for-commands loop.

These tests need no PostgreSQL and no network: the loop is driven with a
fake one-cycle callable and a fake sleep that stops the loop.
"""
import threading
from uuid import uuid4

import pytest

from command_center.agent import run_forever, validate_agent_url
from command_center.errors import DomainError


@pytest.mark.parametrize("url", [
    "https://api.giakhanh.xyz",
    "https://api.giakhanh.xyz:443",
    "https://api.giakhanh.xyz:443/api/v1",
    "http://127.0.0.1:8016",
    "http://localhost:8016",
    "https://127.0.0.1:8016",
])
def test_validate_agent_url_accepts_443_or_loopback(url):
    assert validate_agent_url(url) == url.rstrip("/")


@pytest.mark.parametrize("url,code", [
    ("http://api.giakhanh.xyz", "TLS_REQUIRED"),
    ("http://api.giakhanh.xyz:443", "TLS_REQUIRED"),
    ("https://api.giakhanh.xyz:8443", "OUTBOUND_443_ONLY"),
    ("https://api.giakhanh.xyz:8005", "OUTBOUND_443_ONLY"),
    ("ftp://api.giakhanh.xyz", "TLS_REQUIRED"),
])
def test_validate_agent_url_rejects_non_443_remote(url, code):
    with pytest.raises(DomainError) as err:
        validate_agent_url(url)
    assert err.value.code == code
    assert err.value.status == 422


def test_run_forever_polls_until_stopped():
    stop = threading.Event()
    calls = {"once": 0, "sleeps": []}

    def fake_once(client, agent_id, storage_root):
        calls["once"] += 1
        return {"status": "idle"}

    def fake_sleep(seconds):
        calls["sleeps"].append(seconds)
        if len(calls["sleeps"]) >= 3:
            stop.set()

    result = run_forever(None, uuid4(), ".", poll_interval=5.0,
                         stop_event=stop, sleep=fake_sleep, once=fake_once)
    assert result == {"status": "stopped", "cycles": 3}
    assert calls["once"] == 3
    assert calls["sleeps"] == [5.0, 5.0, 5.0]


def test_run_forever_backs_off_on_errors():
    stop = threading.Event()
    sleeps = []

    def failing_once(client, agent_id, storage_root):
        raise DomainError("AGENT_REQUEST_REJECTED", 503)

    def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) >= 3:
            stop.set()

    result = run_forever(None, uuid4(), ".", poll_interval=5.0,
                         stop_event=stop, sleep=fake_sleep, once=failing_once)
    assert result["status"] == "stopped"
    assert sleeps == [10.0, 20.0, 40.0]
