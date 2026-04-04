"""
simulator/api/routers/pricing.py
CRUD endpoints for the model pricing table.

GET  /api/pricing  → current pricing table
PUT  /api/pricing  → replace pricing table
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from simulator.api.config_manager import ConfigManager
from simulator.api.dependencies import get_config_manager
from simulator.api.models import PricingTableResponse, PricingUpdateRequest

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


@router.get("", response_model=PricingTableResponse)
async def get_pricing(mgr: ConfigManager = Depends(get_config_manager)):
    cfg = mgr.read()
    return PricingTableResponse(pricing=cfg.pricing)


@router.put("", response_model=PricingTableResponse)
async def update_pricing(
    body: PricingUpdateRequest,
    mgr: ConfigManager = Depends(get_config_manager),
):
    cfg = mgr.read()
    new_cfg = cfg.model_copy(update={"pricing": body.pricing})
    mgr.write(new_cfg)
    return PricingTableResponse(pricing=mgr.read().pricing)
