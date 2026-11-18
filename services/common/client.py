import os, httpx
from .observability import DOWNSTREAM, log

async def get_json(service: str, url: str, request_id: str):
    try:
        log("downstream_request", "calling downstream", request_id=request_id, downstream=service)
        async with httpx.AsyncClient(timeout=httpx.Timeout(float(os.getenv("DOWNSTREAM_TIMEOUT", "1.5")), connect=0.5)) as client:
            response = await client.get(url, headers={"X-Request-ID": request_id}); response.raise_for_status()
            log("downstream_response", "downstream response", request_id=request_id, downstream=service, status=response.status_code)
            return response.json(), None
    except httpx.TimeoutException:
        DOWNSTREAM.labels(os.getenv("SERVICE_NAME","unknown"), service, "timeout").inc(); log("downstream_timeout", "downstream timed out", "warning", request_id=request_id, downstream=service)
        return None, "timeout"
    except httpx.HTTPError as e:
        DOWNSTREAM.labels(os.getenv("SERVICE_NAME","unknown"), service, "unavailable").inc(); log("connection_failure", str(e), "warning", request_id=request_id, downstream=service)
        return None, "unavailable"
