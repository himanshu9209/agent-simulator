"""
tests/test_auth.py
Verify _resolve_headers() — env var substitution for OTLP auth headers.
"""
from __future__ import annotations

import os

import pytest

from simulator.telemetry.emitter import _resolve_headers


class TestResolveHeaders:
    def test_empty_dict_returns_empty(self):
        assert _resolve_headers({}) == {}

    def test_literal_value_passthrough(self):
        headers = {"x-api-key": "my-literal-token"}
        assert _resolve_headers(headers) == {"x-api-key": "my-literal-token"}

    def test_multiple_literal_values(self):
        headers = {
            "x-api-key": "token123",
            "x-dataset": "production",
            "content-type": "application/grpc",
        }
        assert _resolve_headers(headers) == headers

    def test_env_var_substitution(self, monkeypatch):
        monkeypatch.setenv("MY_API_KEY", "secret-value-abc")
        headers = {"x-api-key": "${MY_API_KEY}"}
        result = _resolve_headers(headers)
        assert result["x-api-key"] == "secret-value-abc"

    def test_env_var_substitution_multiple(self, monkeypatch):
        monkeypatch.setenv("TEAM_KEY", "team-abc")
        monkeypatch.setenv("DATASET", "my-dataset")
        headers = {
            "x-honeycomb-team": "${TEAM_KEY}",
            "x-honeycomb-dataset": "${DATASET}",
        }
        result = _resolve_headers(headers)
        assert result["x-honeycomb-team"] == "team-abc"
        assert result["x-honeycomb-dataset"] == "my-dataset"

    def test_unset_env_var_returns_empty_string(self):
        env_var = "DEFINITELY_NOT_SET_AGENT_SIM_XYZ_99"
        os.environ.pop(env_var, None)
        headers = {"x-token": f"${{{env_var}}}"}
        result = _resolve_headers(headers)
        assert result["x-token"] == ""

    def test_unset_env_var_logs_warning(self, caplog):
        import logging
        env_var = "AGENT_SIM_UNSET_HEADER_VAR"
        os.environ.pop(env_var, None)
        headers = {"x-token": f"${{{env_var}}}"}
        with caplog.at_level(logging.WARNING, logger="simulator.telemetry.emitter"):
            _resolve_headers(headers)
        assert any(env_var in record.message for record in caplog.records)

    def test_mixed_literal_and_env_var(self, monkeypatch):
        monkeypatch.setenv("SECRET_TOKEN", "resolved-value")
        headers = {
            "x-token": "${SECRET_TOKEN}",
            "x-literal": "plain-text",
        }
        result = _resolve_headers(headers)
        assert result["x-token"] == "resolved-value"
        assert result["x-literal"] == "plain-text"

    def test_dollar_brace_syntax_only(self, monkeypatch):
        """Only ${VAR} triggers substitution — bare $VAR or other patterns do not."""
        monkeypatch.setenv("VAR", "should-not-matter")
        headers = {
            "x-a": "$VAR",          # not substituted
            "x-b": "prefix${VAR}",  # not substituted (doesn't start with ${)
            "x-c": "${VAR}suffix",  # not substituted (doesn't end with })
        }
        monkeypatch.setenv("VAR", "should-not-be-used")
        result = _resolve_headers(headers)
        assert result["x-a"] == "$VAR"
        assert result["x-b"] == "prefix${VAR}"
        assert result["x-c"] == "${VAR}suffix"

    def test_original_dict_not_mutated(self):
        original = {"x-key": "value"}
        original_copy = dict(original)
        _resolve_headers(original)
        assert original == original_copy
