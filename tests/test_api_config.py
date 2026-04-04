"""
tests/test_api_config.py
Integration tests for /api/config (read/write) and /api/config/validate.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from simulator.api.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    src = Path("config/default.yaml")
    dst = tmp_path / "default.yaml"
    shutil.copy(src, dst)
    monkeypatch.setenv("SIMULATOR_CONFIG_PATH", str(dst))
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/config
# ---------------------------------------------------------------------------

class TestGetConfig:
    def test_returns_200(self, client):
        assert client.get("/api/config").status_code == 200

    def test_response_has_yaml_str(self, client):
        data = client.get("/api/config").json()
        assert "yaml_str" in data
        assert isinstance(data["yaml_str"], str)

    def test_yaml_str_contains_agent_profiles(self, client):
        data = client.get("/api/config").json()
        assert "agent_profiles" in data["yaml_str"]

    def test_response_has_path(self, client):
        data = client.get("/api/config").json()
        assert "path" in data
        assert data["path"].endswith(".yaml")


# ---------------------------------------------------------------------------
# PUT /api/config
# ---------------------------------------------------------------------------

class TestUpdateConfig:
    def test_valid_update_returns_200(self, client):
        current = client.get("/api/config").json()["yaml_str"]
        r = client.put("/api/config", json={"yaml_str": current})
        assert r.status_code == 200

    def test_response_is_updated_yaml(self, client):
        current = client.get("/api/config").json()["yaml_str"]
        data = client.put("/api/config", json={"yaml_str": current}).json()
        assert "yaml_str" in data

    def test_invalid_yaml_syntax_returns_422(self, client):
        r = client.put("/api/config", json={"yaml_str": "key: [unclosed"})
        assert r.status_code == 422

    def test_invalid_schema_returns_422(self, client):
        # Valid YAML but wrong schema (missing agent_profiles)
        r = client.put("/api/config", json={"yaml_str": "random_key: true\n"})
        assert r.status_code == 422

    def test_update_change_persists(self, client, tmp_path):
        current = client.get("/api/config").json()["yaml_str"]
        modified = current.replace("concurrency: 200", "concurrency: 5")
        client.put("/api/config", json={"yaml_str": modified})
        reloaded = client.get("/api/config").json()["yaml_str"]
        assert "concurrency: 5" in reloaded

    def test_update_creates_backup(self, client, tmp_path):
        current = client.get("/api/config").json()["yaml_str"]
        client.put("/api/config", json={"yaml_str": current})
        # The backup dir lives next to the config file inside tmp_path
        backups = list((tmp_path / ".backups").glob("*.yaml"))
        assert len(backups) >= 1


# ---------------------------------------------------------------------------
# POST /api/config/validate
# ---------------------------------------------------------------------------

class TestValidateConfig:
    def test_valid_config_returns_valid_true(self, client):
        current = client.get("/api/config").json()["yaml_str"]
        data = client.post("/api/config/validate", json={"yaml_str": current}).json()
        assert data["valid"] is True
        assert data["errors"] == []

    def test_invalid_yaml_returns_valid_false(self, client):
        data = client.post(
            "/api/config/validate", json={"yaml_str": "bad: [yaml: unclosed"}
        ).json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    def test_invalid_schema_returns_valid_false_with_errors(self, client):
        data = client.post(
            "/api/config/validate",
            json={"yaml_str": "agent_profiles:\n  x:\n    llm_model: gpt-4\n"},
        ).json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    def test_validate_does_not_write_file(self, client, tmp_path):
        config_file = tmp_path / "default.yaml"
        original = config_file.read_text(encoding="utf-8")
        # Send something that would fail schema validation
        client.post(
            "/api/config/validate",
            json={"yaml_str": "agent_profiles:\n  x:\n    llm_model: gpt-4\n"},
        )
        assert config_file.read_text(encoding="utf-8") == original

    def test_returns_200_even_for_invalid_input(self, client):
        r = client.post("/api/config/validate", json={"yaml_str": "bad: [yaml"})
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_returns_200(self, client):
        assert client.get("/health").status_code == 200

    def test_health_status_ok(self, client):
        assert client.get("/health").json() == {"status": "ok"}
