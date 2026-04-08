"""sre-agent FastAPI entrypoint.

Bootstrap order (hexagonal layering):
  1. Configure logging (no domain dep)
  2. Init Langfuse (no domain dep)
  3. Bootstrap the container — instantiates all adapters from env vars
  4. (optional) build the FAISS index
  5. Mount API routers — they call get_container() at request time
  6. Mount Prometheus /metrics endpoint
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.api.deps import require_api_key
from app.api.routes_feedback import router as feedback_router
from app.api.routes_health import router as health_router
from app.api.routes_incidents import router as incidents_router
from app.api.routes_webhooks import router as webhooks_router
from app.infrastructure.config import settings
from app.infrastructure.container import bootstrap, get_container
from app.observability.logging import configure as configure_logging
from app.observability.tracing import init_langfuse, verify_langfuse_connection

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(level=settings.log_level)
    init_langfuse(
        enabled=settings.langfuse_enabled,
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    container = bootstrap(settings)
    log.info("container.bootstrapped", extra={"adapters": container.adapter_summary()})

    # Build FAISS index lazily on startup if applicable.
    if settings.context_provider == "faiss":
        from app.adapters.context.faiss_adapter import FAISSContextAdapter

        if isinstance(container.context, FAISSContextAdapter):
            try:
                await container.context.build()
                log.info("faiss.index_built")
            except Exception as e:  # noqa: BLE001
                log.warning("faiss.build_failed", extra={"error": str(e)})

    verify_langfuse_connection()
    log.info("app.started", extra={"stage": "startup", "event": "app_ready"})
    yield
    # cleanup
    if hasattr(container.ticket, "close"):
        await container.ticket.close()
    if hasattr(container.notify, "close"):
        await container.notify.close()
    log.info("app.stopped", extra={"stage": "shutdown"})


app = FastAPI(title="sre-agent", version="0.2.0", lifespan=lifespan)

# ----- Prometheus metrics endpoint (FASE 6.1) -----
try:
    from prometheus_client import make_asgi_app as _make_metrics_app

    metrics_app = _make_metrics_app()
    app.mount("/metrics", metrics_app)
except ImportError:
    log.warning("prometheus_client not installed — /metrics disabled")

# ----- API routers -----
# Health and metrics are intentionally exempt from authentication — they must
# be reachable by load-balancers and monitoring systems without credentials.
app.include_router(health_router)
app.include_router(incidents_router, dependencies=[Depends(require_api_key)])
app.include_router(webhooks_router, dependencies=[Depends(require_api_key)])
app.include_router(feedback_router, dependencies=[Depends(require_api_key)])

# ----- UI routes -----
try:
    from app.api import routes_ui  # type: ignore[attr-defined]
    app.include_router(routes_ui.router)
except ImportError:
    pass  # UI module is optional; routes_ui.py added in FASE 3.6

# ----- Static files -----
_static_dir = Path(__file__).parent / "ui" / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
