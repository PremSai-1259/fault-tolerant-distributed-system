"""Health observer: records outages; Kubernetes remains responsible for recovery."""
import asyncio
import csv
import datetime as dt
import os
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from prometheus_client import Counter, Gauge, Histogram

CHECKS = Counter("failure_detector_checks_total", "Completed health checks", ["service", "result"])
DETECTED = Counter("failure_detector_failures_detected_total", "Declared outages", ["service", "event_type"])
RECOVERED = Counter("failure_detector_recoveries_total", "Observed recoveries", ["service"])
UP = Gauge("failure_detector_service_up", "Latest service health result", ["service"])
DETECTION_TIME = Histogram("failure_detector_detection_duration_seconds", "First failure to declaration", ["service"])
RECOVERY_TIME = Histogram("failure_detector_recovery_duration_seconds", "Declaration to recovery", ["service"])

@dataclass
class State:
    consecutive: int = 0
    failed_at: dt.datetime | None = None
    detected_at: dt.datetime | None = None

@dataclass
class Detector:
    targets: dict[str, str]
    threshold: int = 3
    timeout: float = 1.0
    event_file: Path = field(default_factory=lambda: Path(os.getenv("EVENT_FILE", "experiments/results/failure_events.csv")))
    states: dict[str, State] = field(default_factory=dict)

    def __post_init__(self):
        self.states = {name: State() for name in self.targets}
        self.event_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.event_file.exists() or self.event_file.stat().st_size == 0:
            with self.event_file.open("w", newline="") as handle:
                csv.writer(handle).writerow(["timestamp", "service", "event_type", "first_failure", "detected_at", "recovered_at"])

    async def check(self, name: str, url: str) -> None:
        state, now = self.states[name], dt.datetime.now(dt.UTC)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=self.timeout)) as client:
                response = await client.get(url)
                response.raise_for_status()
            CHECKS.labels(name, "success").inc(); UP.labels(name).set(1)
            if state.detected_at:
                RECOVERY_TIME.labels(name).observe((now - state.detected_at).total_seconds())
                RECOVERED.labels(name).inc(); self.event(name, "recovery_completed", now, state)
            self.states[name] = State()
        except httpx.HTTPError:
            CHECKS.labels(name, "failure").inc(); UP.labels(name).set(0)
            state.consecutive += 1; state.failed_at = state.failed_at or now
            if state.consecutive >= self.threshold and state.detected_at is None:
                state.detected_at = now
                DETECTED.labels(name, "service_unavailable").inc()
                DETECTION_TIME.labels(name).observe((now - state.failed_at).total_seconds())
                self.event(name, "failure_detected", now, state)

    def event(self, name: str, event_type: str, now: dt.datetime, state: State) -> None:
        row = [now.isoformat(), name, event_type, state.failed_at.isoformat() if state.failed_at else "", state.detected_at.isoformat() if state.detected_at else "", now.isoformat() if event_type == "recovery_completed" else ""]
        with self.event_file.open("a", newline="") as handle: csv.writer(handle).writerow(row)
        print({"event_type": event_type, "service": name, "timestamp": now.isoformat(), "failure_timestamp": row[3]})

    async def run(self, interval: float = 5.0) -> None:
        while True:
            await asyncio.gather(*(self.check(name, url) for name, url in self.targets.items()))
            await asyncio.sleep(interval)
