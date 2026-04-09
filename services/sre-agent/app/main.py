"""sre-agent FastAPI entrypoint.

Bootstrap order (hexagonal layering):
  1. Configure logging (no domain dep)
  2. Init Langfuse (no domain dep)
  3. Bootstrap the container — instantiates all adapters from env vars
  4. (optional) build the FAISS index
  5. Mount API routers — they call get_container() at request time
  6. Mount Prometheus /metrics endpoint

Auth (HU-P018):
  Protected routes accept Bearer JWT (primary) or X-API-Key (backward compat).
  Public routes: GET /health, GET /metrics, POST /auth/mock-google-login,
                 GET /context/status.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.routes_auth import router as auth_router
from app.api.routes_context import router as context_router
from app.api.routes_feedback import router as feedback_router
from app.api.routes_health import router as health_router
from app.api.routes_incidents import router as incidents_router
from app.api.routes_llm_config import router as llm_config_router
from app.api.routes_platform_config import router as platform_config_router
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
    # NOTE: bootstrap() already logs "container.bootstrapped" internally — do not repeat it here.

    # Phase 2 — hydrate LLM adapter from DB config (ARC-023).
    # Replaces the Phase 1 stub with the persisted provider+key from llm_config table.
    # Split into two blocks so DB failures and adapter-build failures are distinguishable.
    try:
        db_config = await container.llm_config_provider.get_llm_config()
    except Exception as _db_err:  # noqa: BLE001
        log.warning(
            "container.llm_hydration_skipped_db_unreachable",
            extra={"error": str(_db_err)},
        )
    else:
        try:
            await container.reload_llm_adapter(db_config)
            log.info("container.llm_hydrated_from_db", extra={"provider": db_config.provider})
        except Exception as _build_err:  # noqa: BLE001
            log.error(
                "container.llm_adapter_build_failed_check_config",
                extra={"provider": db_config.provider, "error": str(_build_err)},
            )

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


app = FastAPI(
    title="SRE Incident Triage Agent",
    version="0.3.0",
    lifespan=lifespan,
    description=(
        "6-stage LLM-powered incident triage pipeline. "
        "Protected endpoints accept **Bearer JWT** (primary) or **X-API-Key** "
        "(backward compat for CI/scripts). "
        "Login via `POST /auth/mock-google-login` to get a JWT."
    ),
)

# ----- CORS middleware (HU-P031) -----
# Allows the React SPA (sre-web) to call the API from a different origin.
# Origins are configured via settings.cors_allow_origins — never "*" in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
# Auth routes are public (login) or self-secured via JWT (me, users, logout)
app.include_router(auth_router, prefix="/auth")
# /context/status is public; /context/reindex requires admin/superadmin (enforced per-route)
app.include_router(context_router)
# Protected routes — auth is enforced per-route via Depends (HU-P018)
app.include_router(incidents_router)
app.include_router(webhooks_router)
app.include_router(feedback_router)
# LLM Config hot-reload (HU-P029) — admin/superadmin only
app.include_router(llm_config_router)
# Platform Configuration (HU-P032-A) — admin/superadmin only
app.include_router(platform_config_router)


# ----- OpenAPI dual-auth security schemes (HU-P018) -----
def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Register both auth schemes so Swagger UI shows the "Authorize" button
    # with options for Bearer JWT and API Key.
    schema.setdefault("components", {}).setdefault("securitySchemes", {}).update(
        {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": (
                    "JWT obtained from POST /auth/mock-google-login. "
                    "Paste the access_token value here."
                ),
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": (
                    "Legacy API key (backward compat for CI/scripts). "
                    "Set SRE_API_KEY env var. Default in dev: 'sre-demo-key'."
                ),
            },
        }
    )
    # Apply both schemes globally — individual routes can override.
    schema["security"] = [{"BearerAuth": []}, {"ApiKeyAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi  # type: ignore[method-assign]

# ----- UI routes -----
try:
    from app.api import routes_ui  # type: ignore[attr-defined]
    app.include_router(routes_ui.router)
except ImportError:
    log.warning("ui.routes_not_found — routes_ui.py not present, skipping UI routes")

# ----- Static files -----
_static_dir = Path(__file__).parent / "ui" / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
