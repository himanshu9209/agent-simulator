"""
tests/test_api_profiles.py
Integration tests for /api/profiles CRUD endpoints.

Each test gets its own copy of default.yaml in a tmp directory so tests
are isolated and don't touch the real config file.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from simulator.api.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    src = Path("config/default.yaml")
    dst = tmp_path / "default.yaml"
    shutil.copy(src, dst)
    monkeypatch.setenv("SIMULATOR_CONFIG_PATH", str(dst))
    with TestClient(app) as c:
        yield c


# Minimal valid profile payload used across creation tests
_NEW_PROFILE = {
    "name": "test_agent",
    "profile": {
        "tools": ["search"],
        "llm_model": "gpt-4o-mini",
        "llm_input_tokens": {"mean": 500, "std": 50},
        "llm_output_tokens": {"mean": 100, "std": 20},
        "planning_latency_ms": {"mean": 100, "std": 10},
        "tool_call_count": {"min": 1, "max": 3},
        "failure_rate": 0.02,
        "mix_weight": 1.0,
    },
}

# ---------------------------------------------------------------------------
# GET /api/profiles
# ---------------------------------------------------------------------------

class TestListProfiles:
    def test_returns_200(self, client):
        assert client.get("/api/profiles").status_code == 200

    def test_returns_list_with_total(self, client):
        data = client.get("/api/profiles").json()
        assert "profiles" in data
        assert "total" in data
        assert data["total"] == len(data["profiles"])

    def test_default_config_has_profiles(self, client):
        data = client.get("/api/profiles").json()
        assert data["total"] > 0

    def test_profile_summary_fields(self, client):
        data = client.get("/api/profiles").json()
        p = data["profiles"][0]
        for field in ("name", "llm_model", "tool_count", "attribute_count",
                      "behavioral_signal_count", "mix_weight", "failure_rate"):
            assert field in p, f"missing field: {field}"

    def test_rag_researcher_in_default_config(self, client):
        data = client.get("/api/profiles").json()
        names = [p["name"] for p in data["profiles"]]
        assert "rag_researcher" in names


# ---------------------------------------------------------------------------
# GET /api/profiles/:name
# ---------------------------------------------------------------------------

class TestGetProfile:
    def test_existing_profile_returns_200(self, client):
        assert client.get("/api/profiles/rag_researcher").status_code == 200

    def test_response_has_name_and_profile(self, client):
        data = client.get("/api/profiles/rag_researcher").json()
        assert data["name"] == "rag_researcher"
        assert "profile" in data

    def test_profile_has_llm_model(self, client):
        data = client.get("/api/profiles/rag_researcher").json()
        assert data["profile"]["llm_model"] == "gpt-4o"

    def test_nonexistent_profile_returns_404(self, client):
        assert client.get("/api/profiles/does_not_exist").status_code == 404

    def test_404_detail_mentions_profile_name(self, client):
        data = client.get("/api/profiles/ghost").json()
        assert "ghost" in data["detail"]


# ---------------------------------------------------------------------------
# POST /api/profiles
# ---------------------------------------------------------------------------

class TestCreateProfile:
    def test_create_returns_201(self, client):
        assert client.post("/api/profiles", json=_NEW_PROFILE).status_code == 201

    def test_create_response_has_name_and_profile(self, client):
        data = client.post("/api/profiles", json=_NEW_PROFILE).json()
        assert data["name"] == "test_agent"
        assert data["profile"]["llm_model"] == "gpt-4o-mini"

    def test_created_profile_is_readable(self, client):
        client.post("/api/profiles", json=_NEW_PROFILE)
        r = client.get("/api/profiles/test_agent")
        assert r.status_code == 200

    def test_created_profile_appears_in_list(self, client):
        client.post("/api/profiles", json=_NEW_PROFILE)
        names = [p["name"] for p in client.get("/api/profiles").json()["profiles"]]
        assert "test_agent" in names

    def test_duplicate_name_returns_409(self, client):
        client.post("/api/profiles", json=_NEW_PROFILE)
        r = client.post("/api/profiles", json=_NEW_PROFILE)
        assert r.status_code == 409

    def test_invalid_profile_missing_fields_returns_422(self, client):
        bad = {"name": "bad_agent", "profile": {"tools": []}}
        assert client.post("/api/profiles", json=bad).status_code == 422

    def test_empty_name_returns_422(self, client):
        payload = {**_NEW_PROFILE, "name": ""}
        assert client.post("/api/profiles", json=payload).status_code == 422


# ---------------------------------------------------------------------------
# PUT /api/profiles/:name
# ---------------------------------------------------------------------------

_UPDATE_BODY = {
    "profile": {
        "tools": ["search", "summarise"],
        "llm_model": "gpt-4o-mini",
        "llm_input_tokens": {"mean": 600, "std": 60},
        "llm_output_tokens": {"mean": 120, "std": 25},
        "planning_latency_ms": {"mean": 150, "std": 20},
        "tool_call_count": {"min": 1, "max": 4},
        "failure_rate": 0.03,
        "mix_weight": 2.0,
    }
}


class TestUpdateProfile:
    def test_update_existing_returns_200(self, client):
        r = client.put("/api/profiles/rag_researcher", json=_UPDATE_BODY)
        assert r.status_code == 200

    def test_update_changes_model(self, client):
        client.put("/api/profiles/rag_researcher", json=_UPDATE_BODY)
        data = client.get("/api/profiles/rag_researcher").json()
        assert data["profile"]["llm_model"] == "gpt-4o-mini"

    def test_update_persists_to_disk(self, client):
        client.put("/api/profiles/rag_researcher", json=_UPDATE_BODY)
        # Second GET confirms the change survived the disk round-trip
        data = client.get("/api/profiles/rag_researcher").json()
        assert data["profile"]["mix_weight"] == 2.0

    def test_update_nonexistent_returns_404(self, client):
        r = client.put("/api/profiles/ghost", json=_UPDATE_BODY)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/profiles/:name
# ---------------------------------------------------------------------------

class TestDeleteProfile:
    def test_delete_existing_returns_204(self, client):
        assert client.delete("/api/profiles/rag_researcher").status_code == 204

    def test_deleted_profile_not_found_via_get(self, client):
        client.delete("/api/profiles/rag_researcher")
        assert client.get("/api/profiles/rag_researcher").status_code == 404

    def test_deleted_profile_not_in_list(self, client):
        client.delete("/api/profiles/rag_researcher")
        names = [p["name"] for p in client.get("/api/profiles").json()["profiles"]]
        assert "rag_researcher" not in names

    def test_delete_nonexistent_returns_404(self, client):
        assert client.delete("/api/profiles/ghost").status_code == 404

    def test_delete_reduces_total_count(self, client):
        before = client.get("/api/profiles").json()["total"]
        client.delete("/api/profiles/rag_researcher")
        after = client.get("/api/profiles").json()["total"]
        assert after == before - 1
