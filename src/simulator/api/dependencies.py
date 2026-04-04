"""
simulator/api/dependencies.py
FastAPI dependency functions — thin wrappers that read from app.state.

Using starlette.requests.HTTPConnection as the parameter type so the same
dependency works for both HTTP (Request) and WebSocket endpoints.
"""
from __future__ import annotations

from starlette.requests import HTTPConnection

from simulator.api.config_manager import ConfigManager
from simulator.api.run_manager import RunManager


def get_config_manager(conn: HTTPConnection) -> ConfigManager:
    return conn.app.state.config_manager  # type: ignore[no-any-return]


def get_run_manager(conn: HTTPConnection) -> RunManager:
    return conn.app.state.run_manager  # type: ignore[no-any-return]
