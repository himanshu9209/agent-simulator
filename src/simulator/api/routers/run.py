"""
simulator/api/routers/run.py
Start / stop / status endpoints and WebSocket live-stats stream.

POST   /api/run/start    → start the simulator (returns 409 if already running)
POST   /api/run/stop     → send graceful stop signal
GET    /api/run/status   → current run stats snapshot
WS     /api/run/stream   → streams status JSON every second until disconnect
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from simulator.api.config_manager import ConfigManager
from simulator.api.dependencies import get_config_manager, get_run_manager
from simulator.api.models import (
    RunStartRequest,
    RunStartResponse,
    RunStatus,
    RunStatusResponse,
    RunStopResponse,
)
from simulator.api.run_manager import RunManager

router = APIRouter(prefix="/api/run", tags=["run"])


@router.post("/start", response_model=RunStartResponse)
async def start_run(
    body: RunStartRequest = RunStartRequest(),
    mgr: ConfigManager = Depends(get_config_manager),
    run_mgr: RunManager = Depends(get_run_manager),
):
    if run_mgr.is_running:
        raise HTTPException(status_code=409, detail="A simulation is already running")

    cfg = mgr.read()

    # Apply request-level overrides (duration, concurrency, single profile)
    sim_updates: dict = {}
    if body.duration is not None:
        sim_updates["run_duration_seconds"] = body.duration
    if body.concurrency is not None:
        sim_updates["concurrency"] = body.concurrency
    if sim_updates:
        cfg = cfg.model_copy(
            update={"simulator": cfg.simulator.model_copy(update=sim_updates)}
        )

    if body.profile is not None:
        if body.profile not in cfg.agent_profiles:
            raise HTTPException(
                status_code=404, detail=f"Profile '{body.profile}' not found"
            )
        cfg = cfg.model_copy(
            update={"agent_profiles": {body.profile: cfg.agent_profiles[body.profile]}}
        )

    await run_mgr.start(cfg)
    return RunStartResponse(message="Simulation started", status=RunStatus.RUNNING)


@router.post("/stop", response_model=RunStopResponse)
async def stop_run(run_mgr: RunManager = Depends(get_run_manager)):
    if not run_mgr.is_running:
        return RunStopResponse(message="No simulation running", status=RunStatus.IDLE)
    await run_mgr.stop()
    return RunStopResponse(message="Stop signal sent", status=RunStatus.STOPPING)


@router.get("/status", response_model=RunStatusResponse)
async def run_status(run_mgr: RunManager = Depends(get_run_manager)):
    return RunStatusResponse(**run_mgr.get_status())


@router.websocket("/stream")
async def run_stream(
    websocket: WebSocket,
    run_mgr: RunManager = Depends(get_run_manager),
):
    """Stream a RunStatusResponse-shaped JSON object every second."""
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(run_mgr.get_status())
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        pass
