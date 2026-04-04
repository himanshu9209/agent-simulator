"""
tests/test_api_run.py
Tests for /api/run start/stop/status endpoints and WebSocket stream.

RunManager is injected via app.dependency_overrides so no real simulator
is launched and no OTel collector is needed.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from fastapi.testclient import TestClient

from simulator.api.dependencies import get_run_manager
from simulator.api.main import app
from simulator.api.run_manager import RunManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _idle_status() -> dict:
    return {
        "status": "idle",
        "started_at": None,
        "elapsed_seconds": 0.0,
        "active_agents": 0,
        "sessions_completed": 0,
        "sessions_error": 0,
        "total_cost_usd": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "tool_calls": 0,
        "error": None,
    }


def _running_status() -> dict:
    return {
        "status": "running",
        "started_at": "2024-01-01T00:00:00",
        "elapsed_seconds": 5.0,
        "active_agents": 200,
        "sessions_completed": 120,
        "sessions_error": 2,
        "total_cost_usd": 0.4812,
        "total_input_tokens": 150_000,
        "total_output_tokens": 30_000,
        "tool_calls": 600,
        "error": None,
    }


def _mock_idle_manager() -> MagicMock:
    mgr = MagicMock(spec=RunManager)
    type(mgr).is_running = PropertyMock(return_value=False)
    mgr.start = AsyncMock()
    mgr.stop = AsyncMock()
    mgr.get_status.return_value = _idle_status()
    return mgr


def _mock_running_manager() -> MagicMock:
    mgr = MagicMock(spec=RunManager)
    type(mgr).is_running = PropertyMock(return_value=True)
    mgr.start = AsyncMock(side_effect=RuntimeError("already running"))
    mgr.stop = AsyncMock()
    mgr.get_status.return_value = _running_status()
    return mgr


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _cleanup_overrides():
    """Ensure dependency overrides don't leak between tests."""
    yield
    app.dependency_overrides.pop(get_run_manager, None)


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Client with a REAL (idle) RunManager — for status/shape tests."""
    src = Path("config/default.yaml")
    dst = tmp_path / "default.yaml"
    shutil.copy(src, dst)
    monkeypatch.setenv("SIMULATOR_CONFIG_PATH", str(dst))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_idle(tmp_path, monkeypatch):
    """Client with a MOCKED idle RunManager."""
    src = Path("config/default.yaml")
    dst = tmp_path / "default.yaml"
    shutil.copy(src, dst)
    monkeypatch.setenv("SIMULATOR_CONFIG_PATH", str(dst))
    idle_mgr = _mock_idle_manager()
    app.dependency_overrides[get_run_manager] = lambda: idle_mgr
    with TestClient(app) as c:
        yield c, idle_mgr


@pytest.fixture
def client_running(tmp_path, monkeypatch):
    """Client with a MOCKED running RunManager."""
    src = Path("config/default.yaml")
    dst = tmp_path / "default.yaml"
    shutil.copy(src, dst)
    monkeypatch.setenv("SIMULATOR_CONFIG_PATH", str(dst))
    running_mgr = _mock_running_manager()
    app.dependency_overrides[get_run_manager] = lambda: running_mgr
    with TestClient(app) as c:
        yield c, running_mgr


# ---------------------------------------------------------------------------
# GET /api/run/status — idle baseline
# ---------------------------------------------------------------------------

class TestRunStatus:
    def test_idle_returns_200(self, client):
        assert client.get("/api/run/status").status_code == 200

    def test_idle_status_value(self, client):
        data = client.get("/api/run/status").json()
        assert data["status"] == "idle"

    def test_status_has_all_required_fields(self, client):
        data = client.get("/api/run/status").json()
        required = (
            "status", "started_at", "elapsed_seconds", "active_agents",
            "sessions_completed", "sessions_error", "total_cost_usd",
            "total_input_tokens", "total_output_tokens", "tool_calls", "error",
        )
        for field in required:
            assert field in data, f"missing field: {field}"

    def test_idle_elapsed_is_zero(self, client):
        data = client.get("/api/run/status").json()
        assert data["elapsed_seconds"] == 0.0

    def test_idle_active_agents_is_zero(self, client):
        data = client.get("/api/run/status").json()
        assert data["active_agents"] == 0

    def test_running_status_from_mock(self, client_running):
        client, _ = client_running
        data = client.get("/api/run/status").json()
        assert data["status"] == "running"
        assert data["active_agents"] == 200
        assert data["sessions_completed"] == 120


# ---------------------------------------------------------------------------
# POST /api/run/start
# ---------------------------------------------------------------------------

class TestRunStart:
    def test_start_returns_200(self, client_idle):
        client, _ = client_idle
        assert client.post("/api/run/start", json={}).status_code == 200

    def test_start_response_status_is_running(self, client_idle):
        client, _ = client_idle
        data = client.post("/api/run/start", json={}).json()
        assert data["status"] == "running"

    def test_start_response_has_message(self, client_idle):
        client, _ = client_idle
        data = client.post("/api/run/start", json={}).json()
        assert "message" in data

    def test_start_calls_manager_start(self, client_idle):
        client, mgr = client_idle
        client.post("/api/run/start", json={})
        mgr.start.assert_called_once()

    def test_start_while_running_returns_409(self, client_running):
        client, _ = client_running
        r = client.post("/api/run/start", json={})
        assert r.status_code == 409

    def test_start_unknown_profile_returns_404(self, client_idle):
        client, _ = client_idle
        r = client.post("/api/run/start", json={"profile": "nonexistent_profile"})
        assert r.status_code == 404

    def test_start_with_known_profile_returns_200(self, client_idle):
        client, _ = client_idle
        r = client.post("/api/run/start", json={"profile": "rag_researcher"})
        assert r.status_code == 200

    def test_start_with_duration_override(self, client_idle):
        client, mgr = client_idle
        client.post("/api/run/start", json={"duration": 30})
        # The config passed to start() should have the override applied
        call_args = mgr.start.call_args[0]
        cfg = call_args[0]
        assert cfg.simulator.run_duration_seconds == 30

    def test_start_with_concurrency_override(self, client_idle):
        client, mgr = client_idle
        client.post("/api/run/start", json={"concurrency": 5})
        call_args = mgr.start.call_args[0]
        cfg = call_args[0]
        assert cfg.simulator.concurrency == 5

    def test_start_with_single_profile_filters_profiles(self, client_idle):
        client, mgr = client_idle
        client.post("/api/run/start", json={"profile": "rag_researcher"})
        call_args = mgr.start.call_args[0]
        cfg = call_args[0]
        assert list(cfg.agent_profiles.keys()) == ["rag_researcher"]


# ---------------------------------------------------------------------------
# POST /api/run/stop
# ---------------------------------------------------------------------------

class TestRunStop:
    def test_stop_when_idle_returns_200(self, client_idle):
        client, _ = client_idle
        assert client.post("/api/run/stop").status_code == 200

    def test_stop_when_idle_returns_idle_status(self, client_idle):
        client, _ = client_idle
        data = client.post("/api/run/stop").json()
        assert data["status"] == "idle"

    def test_stop_when_running_returns_200(self, client_running):
        client, _ = client_running
        assert client.post("/api/run/stop").status_code == 200

    def test_stop_when_running_returns_stopping_status(self, client_running):
        client, _ = client_running
        data = client.post("/api/run/stop").json()
        assert data["status"] == "stopping"

    def test_stop_calls_manager_stop_when_running(self, client_running):
        client, mgr = client_running
        client.post("/api/run/stop")
        mgr.stop.assert_called_once()

    def test_stop_does_not_call_manager_stop_when_idle(self, client_idle):
        client, mgr = client_idle
        client.post("/api/run/stop")
        mgr.stop.assert_not_called()


# ---------------------------------------------------------------------------
# WebSocket /api/run/stream
# ---------------------------------------------------------------------------

class TestRunStream:
    def test_stream_accepts_connection(self, client):
        with client.websocket_connect("/api/run/stream") as ws:
            data = ws.receive_json()
            assert data is not None

    def test_stream_first_message_has_status_field(self, client):
        with client.websocket_connect("/api/run/stream") as ws:
            data = ws.receive_json()
            assert "status" in data

    def test_stream_first_message_has_elapsed_seconds(self, client):
        with client.websocket_connect("/api/run/stream") as ws:
            data = ws.receive_json()
            assert "elapsed_seconds" in data

    def test_stream_first_message_status_is_idle(self, client):
        with client.websocket_connect("/api/run/stream") as ws:
            data = ws.receive_json()
            assert data["status"] == "idle"

    def test_stream_sends_multiple_messages(self, client):
        with client.websocket_connect("/api/run/stream") as ws:
            msg1 = ws.receive_json()
            msg2 = ws.receive_json()
            # Both should be well-formed status snapshots
            assert "status" in msg1
            assert "status" in msg2

    def test_stream_mock_running_manager(self, client_running):
        client, _ = client_running
        with client.websocket_connect("/api/run/stream") as ws:
            data = ws.receive_json()
            assert data["status"] == "running"
            assert data["active_agents"] == 200
