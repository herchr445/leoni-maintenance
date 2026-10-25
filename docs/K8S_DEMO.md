# Kubernetes demo — Leoni Maintenance on a local k3s cluster (k3d)

Manual Helm installation of the application on a local k3s cluster, followed by
real resilience tests. Every result below was measured on the cluster, not assumed.

- Date: 25 October 2026
- Cluster: k3d v5.9.0, k3s **v1.35.5+k3s1**, 1 server + 1 agent node (Docker Desktop, Windows 11)
- Tools: kubectl v1.34.1, Helm **v4.3.1**
- Chart: `deploy/helm/leoni` (chart 0.1.0) with `values-local.yaml`
- Images (built by GitHub Actions, public in GHCR, tagged with the short commit SHA):
  `ghcr.io/herchr445/leoni-backend:668754f`, `ghcr.io/herchr445/leoni-frontend:668754f`, `postgres:16.15-alpine`
- Application URL: `http://localhost:8090` (k3d load balancer → Traefik → Ingress)

## Architecture deployed

| Resource | Details |
|---|---|
| `Deployment/leoni-backend` | FastAPI, 2 replicas, uid 10001, init container `wait-for-db`, startup/liveness (`/health`) and readiness (`/ready`) probes |
| `Deployment/leoni-frontend` | React build served by nginx-unprivileged, 2 replicas, uid 101, port 8080 |
| `StatefulSet/leoni-postgres` | PostgreSQL 16.15, 1 replica, uid 70, PVC `data-leoni-postgres-0` (1Gi, `local-path`), PVC retention `Retain` |
| `Service` ×3 | `leoni-backend` :8000, `leoni-frontend` :8080 (ClusterIP), `leoni-postgres` :5432 (headless) |
| `Ingress/leoni` | Traefik: `/api`, `/health`, `/ready` → backend; `/` → frontend |
| `NetworkPolicy/leoni-postgres` | only backend pods may reach PostgreSQL on TCP 5432 |

Security on every pod: `runAsNonRoot`, fixed UID/GID, `seccompProfile: RuntimeDefault`,
`readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, all capabilities dropped,
no service account token mounted. Writable paths are limited to `emptyDir` volumes
(`/tmp`; `/var/run/postgresql` for PostgreSQL) and the database PVC.

## 1. Installation

### 1.1 Namespace and database Secret (never stored in Git)

The chart does not create the Secret: it only references `leoni-db` (key `password`).
The password is generated in PowerShell (letters and digits only, because it is
inserted into the database URL) and sent to `kubectl` through standard input, so it
never appears on a command line, in a file or on screen:

```powershell
kubectl create namespace leoni

$chars = [char[]]'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'
$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create(); $rng.GetBytes($bytes)
$pw = -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
@{ apiVersion = "v1"; kind = "Secret"; type = "Opaque"
   metadata = @{ name = "leoni-db"; namespace = "leoni" }
   data = @{ password = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pw)) } } |
  ConvertTo-Json -Depth 4 | kubectl create -f -
Remove-Variable pw, bytes; $rng.Dispose()
```

Check without revealing the value: `kubectl get secret leoni-db -n leoni` → `DATA 1`, key `password`, 32 characters.

Read it back only when needed:

```powershell
[Text.Encoding]::ASCII.GetString([Convert]::FromBase64String((kubectl get secret leoni-db -n leoni -o jsonpath="{.data.password}")))
```

### 1.2 Helm install

```powershell
helm install leoni deploy/helm/leoni -n leoni -f deploy/helm/leoni/values-local.yaml
```

Startup timeline (all pods Ready after **71 s**, 0 restarts):

| Time | State |
|---|---|
| t+10 s | backend `Init:0/1` (waiting for PostgreSQL), frontend `ContainerCreating`, postgres `Pending` (volume being provisioned) |
| t+40 s | postgres `Running`, first frontend `Running` |
| t+50 s | backend `PodInitializing` (`wait-for-db`: "no response" → "accepting connections") |
| t+71 s | all 5 pods `1/1 Running` |

The only warning event was one expected startup-probe failure (`connection refused`
before uvicorn was listening). PVC `data-leoni-postgres-0` → `Bound`.

## 2. Tests and results

### 2.1 Application through the Ingress (`http://localhost:8090`)

| Request | Result |
|---|---|
| `GET /` | `200 text/html` |
| `GET /assets/index-*.js` | `200 application/javascript`; 0 absolute API URL in the bundle (relative `/api/...`) |
| `GET /tickets/3` (SPA fallback) | `200` |

Work orders created and updated through the API (the same requests as the UI form and status dropdown):

| Step | `/api/stats` |
|---|---|
| empty database | `total 0, open 0, in progress 0, high 0, avg null` |
| 5 tickets created (2 High) | `total 5, open 5, in progress 0, high 2, avg null` |
| #1 → InProgress, #3 → Resolved, #4 → Closed | `total 5, open 2, in progress 1, high 2, avg 0.0` |

The KPIs follow every change (a Resolved High ticket still counts as active, the
average resolution time appears once a ticket is Closed). Filters: `?status=Open` →
tickets 5 and 2, `?priority=High` → 3 and 1, `?status=Foo` → `422`.

Load balancing: 30 × `GET /api/stats` with 3 backend replicas → **10 / 10 / 10** requests per pod.

### 2.2 Health endpoints

```
curl http://localhost:8090/health     → {"status":"ok"}
curl http://localhost:8090/ready      → {"status":"ready"}
curl http://localhost:8090/api/stats  → {"total_tickets":5,"open_tickets":2,"in_progress_tickets":1,"high_priority_tickets":2,"avg_resolution_time_hours":0.0}
```

### 2.3 Self-healing — delete one backend pod

```powershell
kubectl delete pod -n leoni <one backend pod>
```

- The ReplicaSet created the replacement immediately; it was **Ready 6 s** after creation.
- Traffic loop during the test (one request every 0.2 s): **150 / 150 HTTP 200**, no error — the other replica served everything.

### 2.4 Persistence — delete the database pod

```powershell
kubectl delete pod leoni-postgres-0 -n leoni
```

| | Before | After |
|---|---|---|
| `/api/stats` | `total 5, open 2, in progress 1, high 2` | identical |
| Data fingerprint (ids, machines, statuses) | `85c6824ee32e` | `85c6824ee32e` |
| Volume | `pvc-571c5190-…` | same volume |
| Pod UID | `6b136ddc…` | `73a43721…` (new pod) |

- `leoni-postgres-0` was Ready again **5 s** after the delete command; data intact.
- During the outage `/health` stayed `200` (liveness OK → no restart) while the
  readiness probes failed, so the backend pods were removed from traffic and came
  back automatically. Backend restarts: **0**.

### 2.5 Scaling

```powershell
kubectl scale deployment leoni-backend -n leoni --replicas=3
```

3 replicas Ready in **7 s**, spread over both nodes; the Service had 3 endpoints;
30 requests split 10 / 10 / 10.

### 2.6 Rolling update and rollback

```powershell
helm upgrade leoni deploy/helm/leoni -n leoni -f deploy/helm/leoni/values-local.yaml `
  --set backend.image.tag=83dc3fc --set frontend.image.tag=83dc3fc --force-conflicts
kubectl rollout status deployment/leoni-backend -n leoni
helm rollback leoni 2 -n leoni
```

| Revision | Status | Description |
|---|---|---|
| 1 | superseded | Install |
| 2 | superseded | Ingress fix (see 3.1) |
| 3 | failed | Upgrade refused: field conflict on `.spec.replicas` (see 3.2) |
| 4 | superseded | Upgrade to `83dc3fc` (with `--force-conflicts`) — rollouts done in 27 s, data intact |
| 5 | deployed | Rollback to revision 2 → both Deployments back on `668754f`, 2 replicas — rollouts done in 14 s |

Traffic during the rollback (200 requests, one every 0.2 s): **197 × 200, 3 failures**
(one `502`, two time-outs), all within the few seconds of the pod swap (see 3.3).

### 2.7 NetworkPolicy — only the backend can reach PostgreSQL

k3s enforces NetworkPolicies with its embedded controller (log: "Starting network
policy controller v2.6.3-k3s1"; kube-router iptables chains present on both nodes).

| From | To | Result |
|---|---|---|
| temporary pod (no backend labels) | `leoni-postgres:5432` | **blocked** — `pg_isready`: "no response" (exit 2), although DNS resolves `10.42.0.10` |
| same temporary pod | `leoni-backend:8000/health` | allowed — `{"status":"ok"}` (network itself works) |
| backend pod | `leoni-postgres:5432` | allowed — TCP connected in 4 ms; `/ready` (real `SELECT 1`) → `ready` |

```powershell
kubectl run nettest -n leoni --image=postgres:16.15-alpine --restart=Never --rm -i --command -- `
  sh -c 'pg_isready -h leoni-postgres -p 5432 -t 4; wget -qO- -T 4 http://leoni-backend:8000/health'
```

## 3. Problems found during the tests

### 3.1 `/health` and `/ready` returned the frontend page (fixed)

Through the Ingress, `/health` and `/ready` answered with the React `index.html`
instead of JSON, while `/api/...` worked. Traefik does not use the order of the
Ingress paths: it ranks its routes by **rule length** (longest wins). With
`pathType: Exact`, `/ready` became ``Path(`/ready`)`` (14 characters), shorter than
the frontend's ``PathPrefix(`/`)`` (15), and `/health` tied at 15.
Fix: `pathType: Prefix` → ``PathPrefix(`/health`)`` (21) and ``PathPrefix(`/ready`)``
(20) always win. Applied with `helm upgrade` (revision 2); pods were not restarted.

### 3.2 Helm 4 refused an upgrade after `kubectl scale`

Helm 4 applies manifests with **server-side apply**, which records an owner for each
field. `kubectl scale` made `kubectl.exe` the owner of `.spec.replicas`, so the next
`helm upgrade` failed (`conflict with "kubectl.exe" … .spec.replicas`) and left a
partial update (frontend updated, backend not). `--force-conflicts` lets Helm take
the field back; the replica count returned to the chart value (2). Lesson: manual
`kubectl` changes are drift — the chart (later Git, with ArgoCD) is the source of truth.

### 3.3 A few failed requests during a rolling update (proposed fix)

When a pod is replaced, it receives its stop signal at the same moment it is removed
from the Service endpoints, so Traefik can still send it a request for a moment
(3 failures out of 200 during the rollback). Proposed fix: a `preStop` delay
(`lifecycle.preStop.sleep.seconds: 5`, native since Kubernetes 1.30) on the backend
and frontend, so a pod keeps serving while traffic is moved away.

### 3.4 `/ready` timed out instead of answering 503 during a database outage (proposed fix)

The behaviour was correct (pods removed from traffic, not restarted), but `/ready`
hung longer than the 2 s probe timeout instead of returning `503`: the database URL
has no connection timeout, so psycopg waited on a TCP connection to the old pod IP.
Proposed fix: add `?connect_timeout=3` to `DATABASE_URL` in the chart.

### 3.5 Concurrent schema creation at first start (risk, did not occur)

`main.py` runs `create_all()` at import. Two backend replicas starting at the same
instant on an empty database could both try to create the tables and enum types;
one would fail once and restart. It did not happen here (the two containers started
6 s apart). Proposed fix: create the schema once, before the API starts — for example
take a PostgreSQL advisory lock around `create_all()`, or move schema creation to a
dedicated migration step (a Helm hook Job running Alembic migrations).

## 4. State left running

| | |
|---|---|
| Helm release | `leoni`, revision 5, `deployed` |
| Pods | 2 backend, 2 frontend, 1 postgres — all `1/1 Running`, 0 restarts |
| Resources (`kubectl top`) | backend ~58 MiB each, frontend ~13 MiB each, postgres ~25 MiB |
| Data | 5 work orders in PostgreSQL (PVC `data-leoni-postgres-0`) |

Useful commands:

```powershell
kubectl get pods -n leoni
helm history leoni -n leoni
k3d cluster stop leoni     # free RAM; k3d cluster start leoni to resume (data kept)
```

Data safety: `helm uninstall` and `helm upgrade` do not delete the PVC
(it is created by the StatefulSet, not by Helm, and its retention policy is `Retain`).
The data is deleted only by `kubectl delete pvc`, deleting the namespace, or deleting the cluster.
