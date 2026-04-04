"""
simulator/api/routers/config.py
Endpoints to read/write the full config YAML and validate arbitrary YAML.

GET    /api/config           → raw YAML text + path
PUT    /api/config           → validate + overwrite
POST   /api/config/validate  → validate only, returns errors (never writes)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from simulator.api.config_manager import ConfigManager
from simulator.api.dependencies import get_config_manager
from simulator.api.models import (
    ConfigResponse,
    ConfigValidateRequest,
    ConfigValidateResponse,
    ConfigWriteRequest,
)

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=ConfigResponse)
async def get_config(mgr: ConfigManager = Depends(get_config_manager)):
    return ConfigResponse(yaml_str=mgr.read_raw(), path=str(mgr.path))


@router.put("", response_model=ConfigResponse)
async def update_config(
    body: ConfigWriteRequest,
    mgr: ConfigManager = Depends(get_config_manager),
):
    errors = mgr.validate_raw(body.yaml_str)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    mgr.write_raw(body.yaml_str)
    return ConfigResponse(yaml_str=mgr.read_raw(), path=str(mgr.path))


@router.post("/validate", response_model=ConfigValidateResponse)
async def validate_config(
    body: ConfigValidateRequest,
    mgr: ConfigManager = Depends(get_config_manager),
):
    errors = mgr.validate_raw(body.yaml_str)
    return ConfigValidateResponse(valid=len(errors) == 0, errors=errors)
