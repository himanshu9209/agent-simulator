"""
tests/test_errors.py
Verify that ConfigError and format_validation_error produce useful output.
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel, Field, ValidationError

from simulator.errors import ConfigError, format_validation_error


# ---------------------------------------------------------------------------
# Helper model to trigger ValidationError in tests
# ---------------------------------------------------------------------------

class _BoundedModel(BaseModel):
    rate: float = Field(ge=0.0, le=1.0)
    label: str


def _validation_error_for(data: dict) -> ValidationError:
    try:
        _BoundedModel(**data)
        raise AssertionError("Expected ValidationError was not raised")
    except ValidationError as exc:
        return exc


# ---------------------------------------------------------------------------
# ConfigError
# ---------------------------------------------------------------------------

class TestConfigError:
    def test_is_exception_subclass(self):
        assert issubclass(ConfigError, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ConfigError, match="bad value"):
            raise ConfigError("bad value")

    def test_message_preserved(self):
        err = ConfigError("failure_rate must be between 0 and 1")
        assert "failure_rate" in str(err)


# ---------------------------------------------------------------------------
# format_validation_error
# ---------------------------------------------------------------------------

class TestFormatValidationError:
    def test_contains_config_path(self):
        exc = _validation_error_for({"rate": 2.0, "label": "x"})
        msg = format_validation_error(exc, "config/my_agent.yaml")
        assert "config/my_agent.yaml" in msg

    def test_contains_field_name(self):
        exc = _validation_error_for({"rate": 2.0, "label": "x"})
        msg = format_validation_error(exc, "config/test.yaml")
        assert "rate" in msg

    def test_contains_bad_value(self):
        exc = _validation_error_for({"rate": 99.5, "label": "x"})
        msg = format_validation_error(exc, "config/test.yaml")
        assert "99.5" in msg

    def test_contains_hint_about_default_config(self):
        exc = _validation_error_for({"rate": -1.0, "label": "x"})
        msg = format_validation_error(exc, "config/test.yaml")
        assert "config/default.yaml" in msg

    def test_contains_error_symbol(self):
        exc = _validation_error_for({"rate": 2.0, "label": "x"})
        msg = format_validation_error(exc, "config/test.yaml")
        assert "❌" in msg

    def test_multiple_errors_all_present(self):
        # Both fields invalid
        exc = _validation_error_for({"rate": 5.0, "label": 123})  # label wrong type
        msg = format_validation_error(exc, "config/test.yaml")
        # Should mention 'rate' (out of bounds)
        assert "rate" in msg

    def test_returns_string(self):
        exc = _validation_error_for({"rate": 2.0, "label": "x"})
        result = format_validation_error(exc, "config/test.yaml")
        assert isinstance(result, str)
