"""
simulator/api/routers/profiles.py
CRUD endpoints for agent profiles.

GET    /api/profiles          → list all (summary view)
GET    /api/profiles/:name    → get one (full detail)
POST   /api/profiles          → create
PUT    /api/profiles/:name    → update
DELETE /api/profiles/:name    → delete
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from simulator.api.config_manager import ConfigManager
from simulator.api.dependencies import get_config_manager
from simulator.api.models import (
    ProfileCreateRequest,
    ProfileDetailResponse,
    ProfileListResponse,
    ProfileSummary,
    ProfileUpdateRequest,
)
from simulator.config import AgentProfile, BehavioralSignalsSchema

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _summarise(name: str, profile: AgentProfile) -> ProfileSummary:
    obs = profile.observability_attributes
    attr_count = len(obs.session) + len(obs.tool) + len(obs.inference)

    bs: BehavioralSignalsSchema | None = profile.behavioral_signals
    if bs is not None:
        sig_count = sum(
            1
            for k, v in bs.model_dump().items()
            if v is not None and k != "extra"
        ) + len(bs.extra)
    else:
        sig_count = 0

    return ProfileSummary(
        name=name,
        llm_model=profile.llm_model,
        tool_count=len(profile.tools),
        attribute_count=attr_count,
        behavioral_signal_count=sig_count,
        mix_weight=profile.mix_weight,
        failure_rate=profile.failure_rate,
    )


@router.get("", response_model=ProfileListResponse)
async def list_profiles(mgr: ConfigManager = Depends(get_config_manager)):
    cfg = mgr.read()
    summaries = [_summarise(name, p) for name, p in cfg.agent_profiles.items()]
    return ProfileListResponse(profiles=summaries, total=len(summaries))


@router.get("/{name}", response_model=ProfileDetailResponse)
async def get_profile(name: str, mgr: ConfigManager = Depends(get_config_manager)):
    cfg = mgr.read()
    if name not in cfg.agent_profiles:
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    return ProfileDetailResponse(name=name, profile=cfg.agent_profiles[name])


@router.post("", response_model=ProfileDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    body: ProfileCreateRequest,
    mgr: ConfigManager = Depends(get_config_manager),
):
    cfg = mgr.read()
    if body.name in cfg.agent_profiles:
        raise HTTPException(
            status_code=409, detail=f"Profile '{body.name}' already exists"
        )
    new_cfg = cfg.model_copy(
        update={"agent_profiles": {**cfg.agent_profiles, body.name: body.profile}}
    )
    mgr.write(new_cfg)
    return ProfileDetailResponse(name=body.name, profile=body.profile)


@router.put("/{name}", response_model=ProfileDetailResponse)
async def update_profile(
    name: str,
    body: ProfileUpdateRequest,
    mgr: ConfigManager = Depends(get_config_manager),
):
    cfg = mgr.read()
    if name not in cfg.agent_profiles:
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    new_cfg = cfg.model_copy(
        update={"agent_profiles": {**cfg.agent_profiles, name: body.profile}}
    )
    mgr.write(new_cfg)
    return ProfileDetailResponse(name=name, profile=body.profile)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(name: str, mgr: ConfigManager = Depends(get_config_manager)):
    cfg = mgr.read()
    if name not in cfg.agent_profiles:
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
    new_cfg = cfg.model_copy(
        update={"agent_profiles": {k: v for k, v in cfg.agent_profiles.items() if k != name}}
    )
    mgr.write(new_cfg)
