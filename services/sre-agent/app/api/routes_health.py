"""Health endpoint — exposes which adapters are bound."""
from __future__ import annotations

from fastapi import APIRouter

from app.infrastructure.container import get_container
from app.observability.tracing import get_langfuse

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    container = get_container()
    return {
        "status": "ok",
        "stage_count": 6,
        "adapters": container.adapter_summary(),
        "langfuse": "connected" if get_langfuse() is not None else "disabled",
    }
