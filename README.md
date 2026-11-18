# Fault-Tolerant Distributed Computing with Failure Detection and Recovery

Four FastAPI services run on local Kubernetes: `result → {marks, attendance → eligibility}`. A request ID is propagated on every hop. Result responses distinguish business outcomes (`business_ineligible`) from infrastructure errors (`503 downstream_unavailable`); application bugs produce `500`; Kubernetes detects/reconciles container and pod failure.

## What is implemented

- Async HTTP calls with connect/read timeouts, JSON stdout logs, correlation IDs, `/health/live`, `/health/ready`, `/metrics`, graceful lifecycle events, and safe `/admin/fault` latency/5xx/readiness controls.
- Kubernetes Deployments (two replicas), Services, startup/liveness/readiness probes, resource bounds, topology spreading, PDBs, local image policy, ConfigMap, Prometheus, Grafana, Loki, and Alloy DaemonSet.
- An observer-only failure detector with a configurable consecutive-failure threshold. It records detection/recovery; it never replaces pods (Deployment reconciliation does that).
- Guarded, reversible injection commands; a CSV traffic generator and analysis/reports/latency chart generator.

## macOS quick start

Install prerequisites once: `brew install minikube kubectl`; install and start Docker Desktop. Start the required local cluster:

```sh
minikube start --driver=docker --nodes=3 -p ft-demo
minikube profile ft-demo
eval "$(minikube -p ft-demo docker-env)"
make build
make deploy
kubectl -n fault-tolerance rollout status deploy/result
make status
```

`eval ... docker-env` makes images available directly to Minikube. Alternatively run `make load`; do not use both paths. If images have already been loaded, this project can deploy offline with `imagePullPolicy: IfNotPresent`.

In separate terminals:

```sh
make port-forward                                      # result API at :8000
kubectl -n fault-tolerance port-forward svc/grafana 3000:3000 # admin/admin
kubectl -n fault-tolerance port-forward svc/prometheus 9090:9090
python scripts/traffic_generator.py --duration 120 --experiment normal
python scripts/analyze_results.py --experiment normal
```

Inspect a specific container with `kubectl -n fault-tolerance logs deploy/marks --all-containers --tail=100`; query Grafana Explore using `{namespace="fault-tolerance"}` (add labels in Alloy configuration if your Kubernetes log layout lacks them) and search JSON fields such as `request_id`, `event_type`, or `level`.

## Safe experiments

Every action requires `--confirm`; run continuous traffic first. All commands are manual, reproducible, and reversible.

```sh
# E1/E2: delete one replica; Deployment restores it while the other serves
python failure_injection/inject.py delete-pod --service attendance --confirm
# E3/E6: all Marks replicas unavailable, then restore
python failure_injection/inject.py scale-zero --service marks --confirm
python failure_injection/inject.py restore --service marks --confirm
# E4/E5: inject latency or all-request 5xx; clear with value 0
python failure_injection/inject.py latency --service marks --value 2000 --confirm
python failure_injection/inject.py errors --service marks --value 1 --confirm
python failure_injection/inject.py latency --service marks --value 0 --confirm
# E7: deliberately scale two named deployments to zero, then restore each
# E8: worker outage simulation only after selecting its node name:
kubectl get nodes
python failure_injection/inject.py node-drain --service ft-demo-m02 --confirm
kubectl uncordon ft-demo-m02
```

A drain is a graceful eviction, **not** a crash. For an unexpected worker outage, stop the relevant Minikube worker container/instance, observe node `NotReady` and rescheduling where capacity permits, then start it again. Do not target the control plane. PDBs can intentionally delay drain eviction.

## Experiment protocol and calculations

Run normal, single, and simultaneous failures with the traffic generator continuously running; write detector event times to `experiments/results/failure_events.csv`. The report script computes request success availability, mean/p50/p95, and throughput from actual CSV data. Wall-clock availability = `(total time - detector downtime) / total time × 100`; detection = detection minus initiation; recovery = restoration minus detection; recovery success = successful recoveries / attempts. Set SLA with `--sla`; no result is pre-populated or fabricated. Repeat at replicas 1/2/3 by scaling the deployment and label each experiment ID.

## Architecture and recovery semantics

Container failure means its process exits and kubelet restarts it. Pod deletion causes its Deployment to create a new Pod. Worker-node failure makes affected Pods unavailable and the scheduler may reschedule them after node eviction timing/capacity. A service outage is no Ready endpoint behind the Service. Readiness removes an endpoint from Service routing; liveness restarts a sick container. Healthy replicas continue handling Service traffic during a single-pod event.

## Validation and cleanup

```sh
python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
pytest -q
kubectl apply --dry-run=client -f k8s/namespace.yaml
kubectl apply --dry-run=client -f k8s/applications/apps.yaml
make clean
minikube delete -p ft-demo
```

Known local limits: node rescheduling depends on Docker Desktop CPU/RAM; Loki labels vary by Kubernetes log metadata and should be adapted to the installed Alloy version; Prometheus infrastructure metrics require node-exporter/kube-state-metrics (normally installed via the `kube-prometheus-stack` addon/chart) and are not fabricated by this repository.

## Detector, logging, and infrastructure monitoring

The `failure-detector` Deployment is an observer, not a recovery controller. It checks all four Service readiness URLs every `CHECK_INTERVAL` seconds, requires `FAILURE_THRESHOLD` consecutive failed checks, and uses `HEALTH_TIMEOUT` for each request. Its PVC-backed `/events/failure_events.csv` survives a detector container restart. Prometheus scrapes its `/metrics` endpoint for `failure_detector_checks_total`, `failure_detector_failures_detected_total`, `failure_detector_recoveries_total`, `failure_detector_service_up`, and the detection/recovery duration histograms.

Alloy runs on every node and discovers pods in `fault-tolerance`. It adds only bounded Kubernetes labels (`namespace`, `pod`, `container`, and `service`) and decodes CRI log envelopes. Application JSON remains the log line, so search request IDs as JSON fields rather than Loki labels. Loki is explicitly configured by the `loki-config` ConfigMap. Prometheus also scrapes Node Exporter, kube-state-metrics, and the Kubernetes cAdvisor node proxy; cAdvisor panels appear only when the local cluster exposes that endpoint.

### Live validation commands

```sh
make build && make load && make deploy
kubectl -n fault-tolerance rollout status deploy/failure-detector
kubectl -n fault-tolerance get pods,pvc
kubectl -n fault-tolerance port-forward svc/prometheus 9090:9090
kubectl -n fault-tolerance port-forward svc/grafana 3000:3000

# Baseline detector targets and detector event history
curl -s 'http://localhost:9090/api/v1/query?query=failure_detector_service_up'
kubectl -n fault-tolerance exec deploy/failure-detector -- cat /events/failure_events.csv

# Single-pod replacement: normally no service-level detector failure with a second replica.
kubectl -n fault-tolerance delete pod -l app=marks --field-selector=status.phase=Running
kubectl -n fault-tolerance rollout status deploy/marks

# Full service outage: this is the detector test; then restore.
kubectl -n fault-tolerance scale deploy/marks --replicas=0
sleep 20
curl -s 'http://localhost:9090/api/v1/query?query=failure_detector_failures_detected_total'
kubectl -n fault-tolerance scale deploy/marks --replicas=2
kubectl -n fault-tolerance rollout status deploy/marks
sleep 10
kubectl -n fault-tolerance exec deploy/failure-detector -- cat /events/failure_events.csv
```

Send and correlate an actual request:

```sh
curl -i -H 'X-Request-ID: demo-correlation-001' http://localhost:8000/results/S001
# Grafana Explore LogQL: {namespace="fault-tolerance"} | json | request_id="demo-correlation-001"
# Failure logs: {namespace="fault-tolerance"} | json | event_type=~"(injected_failure|downstream_timeout|connection_failure)"
python failure_injection/inject.py errors --service marks --value 1 --confirm
```

Useful PromQL: `100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])))`, `100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)`, `sum(rate(container_cpu_usage_seconds_total{namespace="fault-tolerance",container!=""}[5m])) by (pod,container)`, `kube_deployment_spec_replicas{namespace="fault-tolerance"}`, `kube_deployment_status_replicas_available{namespace="fault-tolerance"}`, and `sum(kube_pod_container_status_restarts_total{namespace="fault-tolerance"}) by (pod,container)`.

### Validation report

| Component | Test | Expected observation | Actual result |
|---|---|---|---|
| Failure Detector | Service outage | One failure event after threshold | NOT VALIDATED — Docker daemon unavailable |
| Failure Detector | Service recovery | One recovery event and reset state | NOT VALIDATED — Docker daemon unavailable |
| Logging | Request-ID search | Result and downstream logs in Loki | NOT VALIDATED — Docker daemon unavailable |
| Infrastructure | Node CPU/memory | Real Node Exporter values | NOT VALIDATED — Docker daemon unavailable |
| Infrastructure | Pod deletion | Replacement and replica metrics visible | NOT VALIDATED — Docker daemon unavailable |
