"""Shared correlation, structured logging, metrics, and controllable test faults."""
import asyncio, json, logging, os, time, uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

SERVICE = os.getenv("SERVICE_NAME", "unknown")
REQUESTS = Counter("ft_http_requests_total", "HTTP requests", ["service", "method", "path", "status"])
LATENCY = Histogram("ft_http_request_duration_seconds", "HTTP latency", ["service", "method", "path"])
DOWNSTREAM = Counter("ft_downstream_errors_total", "Downstream errors", ["service", "downstream", "kind"])
INJECTED = Counter("ft_injected_failures_total", "Injected failures", ["service", "kind"])
READY = Gauge("ft_service_ready", "Readiness state", ["service"])

class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {"timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "service": SERVICE,
                "level": record.levelname, "message": record.getMessage(), "event_type": getattr(record, "event_type", "application")}
        for k in ("request_id", "method", "endpoint", "status", "duration_ms", "downstream", "error", "exception_type"):
            if hasattr(record, k): data[k] = getattr(record, k)
        return json.dumps(data, default=str)

logger = logging.getLogger("ft")
logger.setLevel(logging.INFO)
if not logger.handlers:
    h = logging.StreamHandler(); h.setFormatter(JsonFormatter()); logger.addHandler(h)

class FaultState:
    latency_ms = 0
    error_rate = 0.0
    ready = True
fault = FaultState()

def log(event_type, message, level="info", **extra):
    getattr(logger, level)(message, extra={"event_type": event_type, **extra})

async def maybe_fault(request_id: str):
    if fault.latency_ms:
        await asyncio.sleep(fault.latency_ms / 1000)
    if fault.error_rate > 0 and (uuid.uuid4().int % 10000) < int(fault.error_rate * 10000):
        INJECTED.labels(SERVICE, "http_5xx").inc(); log("injected_failure", "injected HTTP 503", "warning", request_id=request_id)
        return JSONResponse({"error": "injected_failure", "request_id": request_id}, 503)

def install(app: FastAPI):
    @app.middleware("http")
    async def telemetry(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        started = time.perf_counter(); log("request_received", "request received", request_id=request_id, method=request.method, endpoint=request.url.path)
        try:
            if request.url.path not in ("/health/live", "/health/ready", "/metrics", "/admin/fault"):
                injected = await maybe_fault(request_id)
                if injected: response = injected
                else: response = await call_next(request)
            else: response = await call_next(request)
        except Exception as e:
            log("application_error", str(e), "error", request_id=request_id, exception_type=type(e).__name__)
            response = JSONResponse({"error": "internal_error", "request_id": request_id}, 500)
        duration = time.perf_counter() - started; path = request.url.path
        REQUESTS.labels(SERVICE, request.method, path, str(response.status_code)).inc(); LATENCY.labels(SERVICE, request.method, path).observe(duration)
        response.headers["X-Request-ID"] = request_id
        log("request_completed", "request completed", request_id=request_id, method=request.method, endpoint=path, status=response.status_code, duration_ms=round(duration*1000,2))
        return response

    @app.get("/health/live", include_in_schema=False)
    async def live(): return {"status": "live", "service": SERVICE}
    @app.get("/health/ready", include_in_schema=False)
    async def ready():
        READY.labels(SERVICE).set(1 if fault.ready else 0)
        return JSONResponse({"status": "ready" if fault.ready else "not_ready"}, 200 if fault.ready else 503)
    @app.get("/metrics", include_in_schema=False)
    async def metrics(): return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    @app.post("/admin/fault", include_in_schema=False)
    async def configure_fault(payload: dict):
        fault.latency_ms = max(0, int(payload.get("latency_ms", fault.latency_ms)))
        fault.error_rate = min(1, max(0, float(payload.get("error_rate", fault.error_rate))))
        fault.ready = bool(payload.get("ready", fault.ready))
        kind = "latency" if fault.latency_ms else "http_5xx" if fault.error_rate else "cleared"
        INJECTED.labels(SERVICE, kind).inc(); log("injected_failure", "fault configuration changed", "warning", kind=kind)
        return {"latency_ms": fault.latency_ms, "error_rate": fault.error_rate, "ready": fault.ready}

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log("startup", "service started")
    yield
    log("shutdown", "service stopped")
