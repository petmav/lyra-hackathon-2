import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from praetor_api.routers.corpora import router as corpora_router
from praetor_api.routers.evidence import router as evidence_router
from praetor_api.routers.events import router as events_router
from praetor_api.routers.findings import router as findings_router
from praetor_api.routers.hooks import router as hooks_router
from praetor_api.routers.inventory import router as inventory_router
from praetor_api.routers.models import router as models_router
from praetor_api.routers.policy import router as policy_router
from praetor_api.routers.proposed_changes import router as proposed_changes_router
from praetor_api.routers.sandbox import router as sandbox_router
from praetor_api.routers.workflows import router as workflows_router
from praetor_api.services.readiness import runtime_readiness
from praetor_api.settings import get_settings
from praetor_api.ws.streams import router as stream_router

settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Praetor API",
    version="0.1.0",
    description="Control plane API for governed agentic GRC workflows.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "internal server error"},
    )


@app.middleware("http")
async def require_dev_bearer(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    authorization = request.headers.get("authorization", "")
    expected = f"Bearer {settings.dev_bearer}"
    if authorization != expected:
        return JSONResponse(
            status_code=401,
            content={"detail": "missing or invalid bearer token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await call_next(request)


@app.middleware("http")
async def add_runtime_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Praetor-Data-Mode"] = settings.data_mode
    response.headers["X-Praetor-Data-Backend"] = settings.data_backend
    return response


@app.get("/health")
async def health() -> dict[str, bool | str]:
    return {
        "ok": True,
        "data_mode": settings.data_mode,
        "data_backend": settings.data_backend,
    }


@app.get("/runtime/config")
async def runtime_config() -> dict[str, str | bool]:
    return {
        "data_mode": settings.data_mode,
        "data_backend": settings.data_backend,
        "seed_demo_data": settings.seed_demo_data,
        "default_model_provider": settings.default_model_provider,
        "default_model_name": settings.default_model_name,
        "agent_model_mode": settings.agent_model_mode,
        "workflow_execution_mode": settings.workflow_execution_mode,
    }


@app.get("/runtime/readiness")
async def readiness() -> dict:
    return runtime_readiness()


app.include_router(policy_router)
app.include_router(workflows_router)
app.include_router(corpora_router)
app.include_router(events_router)
app.include_router(hooks_router)
app.include_router(findings_router)
app.include_router(proposed_changes_router)
app.include_router(sandbox_router)
app.include_router(evidence_router)
app.include_router(models_router)
app.include_router(inventory_router)
app.include_router(stream_router)
