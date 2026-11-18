import asyncio
import os
from prometheus_client import start_http_server
from .detector import Detector
targets={x:os.getenv(f"{x.upper()}_HEALTH",f"http://{x}-service:8000/health/ready") for x in ("result","marks","attendance","eligibility")}
start_http_server(int(os.getenv("METRICS_PORT","8001")))
asyncio.run(Detector(targets, int(os.getenv("FAILURE_THRESHOLD","3")), float(os.getenv("HEALTH_TIMEOUT","1"))).run(float(os.getenv("CHECK_INTERVAL","5"))))
