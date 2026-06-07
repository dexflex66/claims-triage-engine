from __future__ import annotations

import uuid
from datetime import datetime, timezone
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from db.models import Base
from db.session import SessionLocal, engine
from repositories import audit as audit_repo
from service.observability import configure_logging, metrics_response, observe_http, request_logger
from service.provider_contract import enforce_live_contract, is_live_requested
from service.routes.ops import router as ops_router
from service.routes.audit import router as audit_router
from service.routes.cases import router as cases_router
from service.routes.outcomes import metrics_router, router as outcomes_router
from service.routes.payments import router as payments_router
from service.routes.remittance import case_router as case_remittance_router
from service.routes.remittance import router as remittance_router
from service.routes.review import router as review_router
from service.routes.submission import case_router, queue_router, recon_router
from service.security.key_rotation import validate_key_rotation
from service.security.network import allowlist_enabled, is_ip_allowed, resolve_client_ip
from service.security.production_guard import validate_production_controls
from service.security.transport_controls import validate_transport_controls


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


app = FastAPI(title="Payer-Proof Claims API", version="1.0.0")


@app.on_event("startup")
def startup() -> None:
    configure_logging()
    Base.metadata.create_all(bind=engine)
    # Fail fast when live US connector is configured but contract/credentials are invalid.
    if is_live_requested("US278_BASE_URL"):
        enforce_live_contract("us_278_837")
    if is_live_requested("IN_PREAUTH_BASE_URL"):
        enforce_live_contract("india_preauth")
    validate_transport_controls()
    validate_key_rotation()
    validate_production_controls()


@app.middleware("http")
async def trace_and_audit_middleware(request: Request, call_next):
    start = perf_counter()
    logger = request_logger()
    trace_id = request.headers.get("x-correlation-id") or uuid.uuid4().hex
    request.state.trace_id = trace_id
    request.state.client_ip = resolve_client_ip(
        request.headers.get("x-forwarded-for", ""),
        request.client.host if request.client else "",
    )

    if allowlist_enabled() and not is_ip_allowed(request.state.client_ip):
        return JSONResponse(
            status_code=403,
            content={"detail": "client_ip_not_allowed", "client_ip": request.state.client_ip},
            headers={"x-correlation-id": trace_id},
        )

    try:
        response = await call_next(request)
    except Exception as exc:
        duration = perf_counter() - start
        observe_http(request.method, request.url.path, 500, duration)
        logger.exception(
            "request_failed",
            extra={
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "duration_ms": round(duration * 1000.0, 2),
                "client_ip": request.state.client_ip,
            },
        )
        with SessionLocal() as session:
            try:
                audit_repo.write_event(
                    session,
                    event_type="access",
                    actor_id=request.headers.get("x-actor-id", "unknown"),
                    resource_type="api",
                    resource_id=request.url.path,
                    outcome="error",
                    details={"method": request.method, "error": str(exc)},
                    timestamp_utc=_now(),
                    trace_id=trace_id,
                )
                session.commit()
            except Exception:
                session.rollback()
        raise

    response.headers["x-correlation-id"] = trace_id
    duration = perf_counter() - start
    observe_http(request.method, request.url.path, int(response.status_code), duration)
    logger.info(
        "request_complete",
        extra={
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path,
            "status": int(response.status_code),
            "duration_ms": round(duration * 1000.0, 2),
            "client_ip": request.state.client_ip,
        },
    )

    with SessionLocal() as session:
        try:
            audit_repo.write_event(
                session,
                event_type="access",
                actor_id=request.headers.get("x-actor-id", "unknown"),
                resource_type="api",
                resource_id=request.url.path,
                outcome=str(response.status_code),
                details={"method": request.method},
                timestamp_utc=_now(),
                trace_id=trace_id,
            )
            session.commit()
        except Exception:
            session.rollback()
    return response


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "payer-proof-claims", "version": "1.0.0"}


@app.get("/metrics")
def metrics():
    return metrics_response()


app.include_router(cases_router)
app.include_router(review_router)
app.include_router(case_router)
app.include_router(queue_router)
app.include_router(recon_router)
app.include_router(remittance_router)
app.include_router(case_remittance_router)
app.include_router(payments_router)
app.include_router(outcomes_router)
app.include_router(metrics_router)
app.include_router(ops_router)
app.include_router(audit_router)
