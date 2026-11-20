# Fault-Tolerant Distributed System

A small Kubernetes-hosted student results system used to explore service dependencies, health checks, failure detection, and recovery. Four Python/FastAPI services communicate over HTTP, while Kubernetes maintains replicas and routes requests to ready pods. A separate observer detects service outages and records detection and recovery events.

## Services and request flow

```text
Client → Result → Marks
                → Attendance → Eligibility
```

`GET /results/{student_id}` calls Marks and Attendance concurrently. Attendance calls Eligibility to evaluate the 75% attendance threshold. The sample data contains students `S001`, `S002`, and `S003`; other IDs return a business 404. The result response includes marks, average, attendance, eligibility, outcome, and request ID.

Each service exposes `/health/live`, `/health/ready`, and `/metrics`. Requests carry an `X-Request-ID` across service calls and are logged as JSON. A downstream timeout or unavailable service becomes a 503; an unknown student is a 404; eligible and business-ineligible results are normal responses.

## Repository layout

- `services/` — Result, Marks, Attendance, Eligibility, and shared HTTP/observability code.
- `failure_detector/` — Periodically checks service readiness and records outage/recovery events.
- `failure_injection/` — Explicitly invoked Kubernetes pod, scale, node-drain, latency, and error injection commands.
- `scripts/` — HTTP traffic generator and CSV analysis/report generator.
- `k8s/` — Namespace, application and detector workloads, Prometheus/Grafana, and log collection manifests.
- `monitoring/` — Prometheus, Loki, Alloy, and Grafana configuration and dashboards.
- `tests/` — Unit and observability tests.

## Requirements

For the full Kubernetes setup, install Docker, Minikube, and `kubectl`. The provided Minikube example uses the Docker driver and three nodes. Python 3.12 is used in the application image; local development requires Python 3.10 or newer.

## Run on Minikube

From the repository root, start the cluster and build the service images inside Minikube's Docker environment:

```sh
minikube start --driver=docker --nodes=3 -p ft-demo
minikube profile ft-demo
eval "$(minikube -p ft-demo docker-env)"
make build
make deploy
kubectl -n fault-tolerance rollout status deploy/result
make status
```

`make build` creates `ft/result:local`, `ft/marks:local`, `ft/attendance:local`, `ft/eligibility:local`, and `ft/failure-detector:local`. To build with the host Docker daemon instead, omit `docker-env` and run `make load` after `make build` to transfer the images into Minikube. The deployments use `imagePullPolicy: IfNotPresent`.

`make deploy` applies the namespace, applications, monitoring, and logging manifests. Each application service runs two replicas, with probes, resource requests/limits, and disruption budgets where configured. The failure detector runs as one replica and stores its CSV event history on a PVC.

## Access the application and dashboards

Run each port forward in its own terminal:

```sh
make port-forward
kubectl -n fault-tolerance port-forward svc/prometheus 9090:9090
kubectl -n fault-tolerance port-forward svc/grafana 3000:3000
```

The result API is at `http://localhost:8000`; Prometheus is at `http://localhost:9090`; Grafana is at `http://localhost:3000` (default Grafana credentials are `admin` / `admin`). Grafana is provisioned with application-health, fault-tolerance, and infrastructure dashboards. Node Exporter, kube-state-metrics, Prometheus, Loki, Grafana, and Alloy are deployed by the repository's manifests.

Example request and correlated log query:

```sh
curl -i -H 'X-Request-ID: demo-correlation-001' http://localhost:8000/results/S001
```

In Grafana Explore, select Loki and query `{namespace="fault-tolerance"} | json | request_id="demo-correlation-001"`. Application JSON fields remain in the log line; the configured Loki labels include Kubernetes metadata such as namespace, pod, container, and service.

## Generate traffic and analyze results

The traffic generator defaults to two concurrent requests at two rounds per second for 60 seconds. One in every five requests uses an unknown student ID to include a business 404 in the sample:

```sh
python scripts/traffic_generator.py --duration 120 --experiment normal
python scripts/analyze_results.py --experiment normal
```

Traffic is written to `experiments/results/traffic.csv`. The analysis script reads that CSV and writes a JSON summary, Markdown report, and latency histogram under `experiments/reports/`. It reports request success rate, latency percentiles, mean latency, and throughput. This request success rate is not wall-clock availability; use the detector event timestamps to study outage and recovery intervals. Both scripts accept `--help` for their available options. The output folders/files are created when the scripts run.

The failure detector checks the four `/health/ready` endpoints every five seconds by default and declares an outage after three consecutive failed checks. Its event history is written to `/events/failure_events.csv` in Kubernetes and is backed by the `failure-detector-events` PVC. Detector Prometheus metrics include check counts, detected failures, recoveries, latest service health, and detection/recovery durations.

## Failure experiments

Run traffic in one terminal while injecting a scenario in another. Every injection command requires `--confirm`:

```sh
# Delete one Marks pod; its Deployment should replace it.
python failure_injection/inject.py delete-pod --service marks --confirm

# Simulate a complete service outage and restore two replicas.
python failure_injection/inject.py scale-zero --service marks --confirm
python failure_injection/inject.py restore --service marks --confirm

# Inject latency or 100% HTTP 5xx responses; clear either setting with value 0.
python failure_injection/inject.py latency --service marks --value 2000 --confirm
python failure_injection/inject.py latency --service marks --value 0 --confirm
python failure_injection/inject.py errors --service marks --value 1 --confirm
python failure_injection/inject.py errors --service marks --value 0 --confirm
```

For `scale-zero`, restore the service after the observation period. `restore` sets the deployment to two replicas. The latency and error scenarios configure a selected running pod through its `/admin/fault` endpoint; Kubernetes deployments have multiple pods, so requests may reach a pod that was not configured. These are experimental controls, not production security controls.

The `node-drain` scenario runs `kubectl drain` for the supplied node name. This is a graceful eviction, not a simulated sudden node crash; PDBs can delay it. Inspect node names first with `kubectl get nodes`, and uncordon a drained node with `kubectl uncordon <node>` when finished. Do not drain the control plane for this exercise.

Kubernetes performs workload recovery: it restarts failed containers, replaces deleted pods, and schedules replacement pods when capacity allows. The detector only observes and records health transitions; it does not restart or replace workloads. Readiness controls Service endpoints, while liveness triggers container restarts when its probe fails.

## Local development and validation

Create a virtual environment and install development dependencies:

```sh
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -q
```

The `make test` target runs `pytest -q`. Python dependencies include FastAPI, Uvicorn, HTTPX, Prometheus client, pandas, NumPy, and Matplotlib. The Dockerfile builds the same application image for each service using `SERVICE_MODULE` and `SERVICE_NAME` deployment environment variables.

## Cleanup

Remove the application and monitoring namespace with:

```sh
make clean
```

To remove the local cluster as well:

```sh
minikube delete -p ft-demo
```
