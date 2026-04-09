"""Context management endpoints (HU-P030).

GET  /context/status          — read-only index status panel (public, AC-05, AC-09, AC-11)
GET  /context/reindex/status  — reindex job status (any authenticated user)
POST /context/reindex         — trigger background re-index (admin/superadmin only, AC-04)

Auth (HU-P018, ARC-022):
  /context/status          → PUBLIC — UI polls this without credentials.
  /context/reindex/status  → Bearer JWT or X-API-Key.
  /context/reindex         → admin or superadmin role required.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import get_current_user_or_api_key, require_role
from app.domain.entities.user import User, UserRole
from app.infrastructure.container import get_container
from app.infrastructure.config import settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/context", tags=["context"])

# ---------------------------------------------------------------------------
# Reindex job registry — tracks in-progress background jobs
# ---------------------------------------------------------------------------
_reindex_jobs: dict[str, dict[str, Any]] = {}
_reindex_lock = asyncio.Lock()
MAX_REINDEX_JOBS = 100


# ---------------------------------------------------------------------------
# GET /context/status — AC-05, AC-09, AC-11
# ---------------------------------------------------------------------------

@router.get("/status")
async def context_status() -> dict:
    """Return the current state of the RAG context index.

    Response fields:
      provider        — active adapter name ("github", "faiss", "static")
      status          — "ready" | "fallback" | "building"
      indexed_files   — number of source files included in the index
      total_chunks    — number of text chunks embedded in the FAISS index
      index_path      — filesystem path of the FAISS index file
      last_indexed_at — ISO-8601 UTC timestamp of last successful index build
      repo_url        — display URL of the eShop repository
    """
    container = get_container()
    context = container.context

    # GithubContextAdapter exposes get_index_status(); other adapters return a
    # minimal status dict so the endpoint always responds with the same shape.
    if hasattr(context, "get_index_status"):
        return context.get_index_status()  # type: ignore[union-attr]

    # Fallback shape for non-github providers
    return {
        "provider": getattr(context, "name", "unknown"),
        "status": "ready",
        "indexed_files": 0,
        "total_chunks": 0,
        "index_path": str(settings.faiss_index_path),
        "last_indexed_at": None,
        "repo_url": settings.eshop_repo_url,
    }


# ---------------------------------------------------------------------------
# POST /context/reindex — AC-04, BR-03
# ---------------------------------------------------------------------------

@router.post("/reindex")
async def trigger_reindex(
    background_tasks: BackgroundTasks,
    _current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> dict:
    """Trigger a background index reload from disk.

    Returns immediately with a job_id. The index is swapped atomically once
    the reload completes so in-flight triage requests are not interrupted (BR-03).

    Note: this endpoint reloads a pre-existing index file written by the build
    script (scripts/build_eshop_index.py). It does NOT re-download the repo.
    For a full re-download + re-index, rebuild the Docker image.
    """
    container = get_container()
    context = container.context

    if not hasattr(context, "reindex"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Active context provider '{getattr(context, 'name', 'unknown')}' "
                "does not support reindex. Set CONTEXT_PROVIDER=github."
            ),
        )

    job_id = str(uuid.uuid4())
    async with _reindex_lock:
        if len(_reindex_jobs) >= MAX_REINDEX_JOBS:
            oldest = next(iter(_reindex_jobs))
            del _reindex_jobs[oldest]
        _reindex_jobs[job_id] = {"status": "indexing", "started_at": _now_iso(), "error": None}

    async def _run_reindex(jid: str) -> None:
        try:
            await context.reindex()  # type: ignore[union-attr]
            async with _reindex_lock:
                _reindex_jobs[jid]["status"] = "ok"
                _reindex_jobs[jid]["completed_at"] = _now_iso()
            log.info("context.reindex_completed", extra={"job_id": jid})
        except Exception as exc:  # noqa: BLE001
            async with _reindex_lock:
                _reindex_jobs[jid]["status"] = "error"
                _reindex_jobs[jid]["error"] = str(exc)
            log.error("context.reindex_failed", extra={"job_id": jid, "error": str(exc)})

    background_tasks.add_task(_run_reindex, job_id)
    log.info("context.reindex_triggered", extra={"job_id": job_id})
    return {"status": "indexing", "job_id": job_id}


# ---------------------------------------------------------------------------
# GET /context/reindex/status — AC-09
# ---------------------------------------------------------------------------

@router.get("/reindex/status")
async def reindex_status(
    _current_user: User = Depends(get_current_user_or_api_key),
) -> dict:
    """Return aggregated reindex job status.

    If no job has run, returns status "ok" (no reindex has been requested).
    If the most recent job is still running, returns "indexing".
    """
    if not _reindex_jobs:
        return {
            "status": "ok",
            "files_processed": 0,
            "files_total": 0,
            "started_at": None,
            "completed_at": None,
            "error_message": None,
        }

    # Return the most recently started job
    latest_key = max(_reindex_jobs, key=lambda k: _reindex_jobs[k].get("started_at", ""))
    job = _reindex_jobs[latest_key]

    # Enrich with live chunk counts if available
    container = get_container()
    context = container.context
    total_chunks = 0
    if hasattr(context, "get_index_status"):
        info = context.get_index_status()  # type: ignore[union-attr]
        total_chunks = info.get("total_chunks", 0)

    return {
        "status": job["status"],
        "files_processed": total_chunks,  # best proxy available at runtime
        "files_total": total_chunks,
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "error_message": job.get("error"),
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(tz=timezone.utc).isoformat()
