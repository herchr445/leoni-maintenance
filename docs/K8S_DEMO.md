# Kubernetes demo — Leoni Maintenance on a local k3s cluster (k3d)

Manual Helm installation of the application on a local k3s cluster, followed by
real resilience tests. Every result below was measured on the cluster, not assumed.

- Dates: first run 25 October 2026 (sections 1–3), fixes and final run 29 October 2026 (section 4)
- Cluster: k3d v5.9.0, k3s **v1.35.5+k3s1**, 1 server + 1 agent node (Docker Desktop, Windows 11)
- Tools: kubectl v1.34.1, Helm **v4.3.1**
- Chart: `deploy/helm/leoni` (chart 0.1.0) with `values-local.yaml`
- Images (built by GitHub Actions, public in GHCR, tagged with the short commit SHA):
  first run `668754f`; **final run `298b48d`** (includes the three fixes of section 4); `postgres:16.15-alpine`
- Application URL: `http://localhost:8090` (k3d load balancer → Traefik → Ingress)

**Final results at a glance** (details in section 4):

| Test | Result |
|---|---|
| Rolling updates + rollbacks under continuous traffic | **0 failed requests out of 904** (p99 latency 31 ms) |
| `/ready` with PostgreSQL stopped | **503 in 7 ms (median), 25 ms max** — target ≈ 3 s |
| Database pod deleted / stopped | data intact, back in **5 s**, 0 backend restarts |
| Backend pod deleted | replacement Ready in **6 s**, 150/150 requests OK |
| Two backends cold-started together on an empty database | **0 restarts in 10 pod starts** (advisory lock) |
| NetworkPolicy | only backend pods reach PostgreSQL:5432 |

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

### 3.3 A few failed requests during a rolling update (fixed — see 4.1)

When a pod is replaced, it receives its stop signal at the same moment it is removed
from the Service endpoints, so Traefik can still send it a request for a moment
(3 failures out of 200 during the rollback). Fixed with a `preStop` delay on the
backend and frontend: 0 failures out of 904 requests in the final run.

### 3.4 `/ready` timed out instead of answering 503 during a database outage (fixed — see 4.2)

The behaviour was correct (pods removed from traffic, not restarted), but `/ready`
hung longer than the 2 s probe timeout instead of returning `503`. Two causes were
found and fixed: no connection timeout in the database URL, and a slow DNS failure
of the short service name. Final result: `503` in 7 ms (median).

### 3.5 Concurrent schema creation at first start (fixed — see 4.3)

`main.py` ran `create_all()` at import. Two backend replicas starting at the same
instant on an empty database could both try to create the tables and enum types;
one would fail once and restart. It did not happen in the first run (the two
containers started 6 s apart), but a deterministic test reproduced it 10 times out
of 10. Fixed with a PostgreSQL advisory lock around the schema creation.

## 4. Fixes applied and final results (29 October 2026)

The three problems of 3.3–3.5 were fixed in separate commits, the backend image was
rebuilt by GitHub Actions (tag `298b48d`), the tag was set in `values-local.yaml`
(a commit touching only `deploy/`, so neither CI pipeline is triggered), and the
release was upgraded with `helm upgrade` (revision 15). All tests below ran on `298b48d`.

### 4.1 Zero-downtime rolling updates — `preStop` drain

Fix: `lifecycle.preStop.sleep.seconds: 5` (native Kubernetes action, no binary needed in
the image) on the backend and frontend, with an explicit `terminationGracePeriodSeconds: 30`.
Measured shutdown after the stop signal: uvicorn **0.55 s**, nginx **0.37 s** (graceful
`SIGQUIT`), so 5 s + ~0.6 s stays far below the 30 s grace period. The chart refuses to
render if the `preStop` delay is not lower than the grace period.

Test: one `GET /api/stats` every 0.2 s through the Ingress during each rollout.

| Rollout | Requests | Failed | Slowest |
|---|---|---|---|
| upgrade `668754f` → `298b48d` (revision 15) | 140 | **0** | 36 ms |
| cycle 1: upgrade to `668754f` / rollback to rev. 15 | 130 / 125 | **0 / 0** | 34 ms |
| cycle 2: upgrade / rollback | 124 / 128 | **0 / 0** | 32 ms |
| cycle 3: upgrade / rollback | 129 / 128 | **0 / 0** | 33 ms |
| **Total** | **904** | **0** | p99 31 ms |

Each rollout took 14–16 s (78 s for the first one, which included pulling the new images).
Before the fix: 3 failures out of 200 requests during a single rollback.

### 4.2 Fast `503` when the database is down — connection timeout and full DNS name

Fix, in two parts found by measurement:

1. `?connect_timeout=3` in `DATABASE_URL`: a connection attempt to an unreachable
   address gives up after 3 s instead of hanging. Alone, this gave `503` in 4–6 s.
2. Timing DNS inside a backend pod with PostgreSQL stopped showed why: the short name
   `leoni-postgres` took **4.01 s** to fail (the query left the cluster's DNS zone),
   while the full name `leoni-postgres.leoni.svc.cluster.local` failed in **0.00 s**.
   The chart now uses the full name (`clusterDomain` in `values.yaml`).

Test: `kubectl scale statefulset leoni-postgres --replicas=0`, then `/ready` every second.

| | `/ready` with PostgreSQL stopped |
|---|---|
| Before the fixes | no answer within the 2 s probe timeout |
| `connect_timeout` only | `503` in 4–6 s |
| **Final (`298b48d`)** | **12 / 12 calls → `503 {"detail":"Database not ready"}`, median 7 ms, max 25 ms** |

After `--replicas=1`: `/ready` OK again in **5 s**, same data fingerprint (`85c6824ee32e`),
0 backend restarts. `/health` stays `200` throughout, so pods are taken out of traffic
but never restarted.

### 4.3 Concurrent schema creation — PostgreSQL advisory lock

Fix: `create_schema()` in `database.py`. With PostgreSQL it runs one transaction:
`SELECT pg_advisory_xact_lock(<fixed id>)`, then `create_all()` on the same connection,
then commit (which releases the lock automatically). The first replica creates the
schema; the others wait, then find the tables and do nothing. With SQLite (tests,
local development, Docker Desktop deployment) it is a plain `create_all()`.
Two unit tests cover both paths (33 tests, 100 % coverage).

Why an advisory lock and not Alembic yet: it fixes exactly this race in a few lines with
no new dependency. Alembic's value is evolving an existing schema (adding or renaming
columns), which needs migration scripts and a dedicated Job before the API starts; it
becomes worth it when the data model starts to change.

| Test | Without the lock | With the lock |
|---|---|---|
| Deterministic: 2 threads released by a barrier, empty PostgreSQL, 10 rounds | **10 / 10 rounds with a failed start** (`UniqueViolation` on `CREATE TYPE`) | **0 / 10** |
| Kubernetes: temporary namespace, backend scaled 0 → 2 on an emptied database, 5 rounds (both init containers finished in the same second every time) | 0 restarts in 10 pod starts | **0 restarts in 10 pod starts** |

The cold starts in the cluster never hit the race even without the lock: the collision
window is a few milliseconds, while the starts are only synchronised to the second.
The deterministic test is the one that proves the lock removes the race. The temporary
namespace was deleted afterwards; `helm uninstall` kept its PVC, as designed, and only
deleting the namespace removed it.

### 4.4 CI path filters

A commit touching only `docs/` or `deploy/` does not trigger the Azure DevOps pipeline
(`trigger.paths.exclude`) nor the GitHub Actions image build (`paths-ignore`): nothing
changes for the Docker Desktop deployment or the images.

## 5. State left running

| | |
|---|---|
| Helm release | `leoni`, revision 21, `deployed`, images `298b48d` |
| Pods | 2 backend, 2 frontend, 1 postgres — all `1/1 Running`, 0 restarts |
| Resources (`kubectl top`) | backend ~58 MiB each, frontend ~13 MiB each, postgres ~21 MiB |
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
