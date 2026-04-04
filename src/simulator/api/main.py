"""
simulator/api/main.py
FastAPI application entry point for the Phase 8a REST + WebSocket API.

Start with:
    uvicorn simulator.api.main:app --host 0.0.0.0 --port 8000 --reload

Environment variables:
    SIMULATOR_CONFIG_PATH   Path to the config YAML (default: config/default.yaml)
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from simulator.api.config_manager import ConfigManager
from simulator.api.run_manager import RunManager
from simulator.api.routers import config, pricing, profiles, run


@asynccontextmanager
async def lifespan(app: FastAPI):
    config_path = os.environ.get("SIMULATOR_CONFIG_PATH", "config/default.yaml")
    app.state.config_manager = ConfigManager(config_path)
    app.state.run_manager = RunManager()
    yield
    # Graceful shutdown: stop any in-flight simulation
    manager: RunManager = app.state.run_manager
    if manager.is_running:
        await manager.stop()


app = FastAPI(
    title="Agent Simulator API",
    description=(
        "REST + WebSocket backend for the agent-simulator Web UI (Phase 8a). "
        "Manages profiles, config, pricing, and live simulation runs."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles.router)
app.include_router(config.router)
app.include_router(run.router)
app.include_router(pricing.router)


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok"}
