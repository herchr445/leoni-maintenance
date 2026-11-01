# Kubernetes demo — Leoni Maintenance on a local k3s cluster (k3d)

- **Part A** — a 5-minute live demo script for interviews.
- **Part B** — the detailed test record: installation, resilience tests, problems found,
  fixes, ArgoCD and the full GitOps loop. Every result was measured on the cluster, not assumed.

# Part A — 5-minute live demo

Message to convey: *a `git push` reaches a Kubernetes cluster with no manual command,
only after blocking quality and security gates, and the cluster repairs itself.*

## A.1 Preparation (before the interview, ~15 min)

The full GitOps loop takes about 7 minutes, too long to wait for live: **start it before
the interview** and show the result during the demo.

```powershell
# 1. Cluster and ArgoCD up (k3d cluster start leoni if it was stopped)
kubectl get nodes                                  # 2 nodes Ready
kubectl get application leoni -n argocd            # Synced / Healthy
kubectl get pods -n leoni                          # 5 pods 1/1 Running

# 2. ~10 min before: one visible change, pushed to both remotes
#    (e.g. the subtitle in frontend/src/App.jsx)
git commit -am "demo: visible change" ; git push origin main ; git push github main

# 3. Open the tabs, in this order
#    http://localhost:8090                                      application (k3s)
#    https://localhost:8443                                     ArgoCD (needs the port-forward below)
#    https://github.com/herchr445/leoni-maintenance/actions     GitHub Actions run
#    https://sonarcloud.io/dashboard?id=herchr445_leoni-maintenance
#    https://dev.azure.com/RAMIHERCH/leoni-maintenance/_build   Azure DevOps pipeline
kubectl port-forward svc/argocd-server -n argocd 8443:443      # separate terminal, keep open
```

Have this file open on the measured results (Part B) in case of detailed questions.
After the interview: `git revert HEAD` and push both remotes (same loop, back to the original text).

## A.2 Script

| Time | Show | Say |
|---|---|---|
| **0:00–0:40** | `localhost:8090`: create a work order, change its status, KPIs update | "A maintenance ticketing app for a wiring-harness plant: FastAPI, React, PostgreSQL. Built during my internship with an Azure DevOps pipeline to Docker Desktop; I then extended it to Kubernetes and GitOps." |
| **0:40–1:40** | GitHub Actions run of the demo commit: 3 jobs | "Every push runs the tests (33, 100 % coverage), Ruff and Bandit, then a **blocking** SonarCloud Quality Gate. Then both images are built and a **blocking** Trivy check stops anything with a fixable CRITICAL CVE — it really stopped a deployment once, for a brotli CVE in the nginx base image. Images go to GHCR, tagged with the commit SHA. The last job is a bot commit that writes the new tag into Git." |
| **1:40–2:40** | ArgoCD: resource tree, then *History and rollback* | "ArgoCD runs in the cluster and polls Git. It saw the bot commit and rolled out the new images — no `kubectl` from me. Git is the source of truth: rolling back is a `git revert`. Push to live: 6 min 48 s to 8 min 09 s, measured; half of it is ArgoCD's 3-minute polling, because GitHub can't send a webhook to a laptop." Reload `localhost:8090`: the change is live. |
| **2:40–3:40** | Terminal: drift and self-healing | Commands below. "If someone changes the cluster by hand, ArgoCD reverts it in about 2 seconds. If a pod dies, Kubernetes replaces it — 6 s measured, with 0 failed requests because the second replica serves the traffic." |
| **3:40–4:30** | Terminal: security | "All pods run as non-root with a read-only filesystem and no Linux capabilities. A NetworkPolicy lets only the backend reach PostgreSQL. The DB password is a Kubernetes Secret that never went into Git; Gitleaks scans the whole history on every build." Show the NetworkPolicy test below. |
| **4:30–5:00** | README *Measured results* table | "Rolling updates: 0 failed requests out of 904. Database down: `/ready` answers 503 in 7 ms so traffic is moved away instead of hanging. And everything I hit along the way is documented in the troubleshooting table." |

Commands for 2:40–4:30 (PowerShell):

```powershell
# Drift: Git says 2 replicas
kubectl scale deployment leoni-backend -n leoni --replicas=5
kubectl get deployment leoni-backend -n leoni -w     # back to 2 in ~2 s, Ctrl+C

# Self-healing: delete one backend pod
kubectl get pods -n leoni -l app.kubernetes.io/component=backend
kubectl delete pod -n leoni <one backend pod>
kubectl get pods -n leoni -w                          # replacement Ready in ~6 s, Ctrl+C

# NetworkPolicy: a pod without the backend labels cannot reach PostgreSQL
kubectl run nettest -n leoni --image=postgres:16.15-alpine --restart=Never --rm -i --command -- `
  sh -c 'pg_isready -h leoni-postgres -p 5432 -t 4; wget -qO- -T 4 http://leoni-backend:8000/health'
#   → "no response" for PostgreSQL, {"status":"ok"} for the backend
```

## A.3 Likely questions

| Question | Short answer |
|---|---|
| Why k3d and not a cloud cluster? | Free, runs on the existing Docker Desktop, real k3s; the same chart would run on AKS/EKS. |
| Why two pipelines? | Azure DevOps was the internship deliverable (deploys on the PC) and stays unchanged; GitHub Actions + ArgoCD is the Kubernetes path. Path filters keep them independent. |
| Why polling and not a webhook? | GitHub cannot reach a cluster on a laptop. In production: webhook or a shorter `timeout.reconciliation`. |
| How do you avoid an infinite loop with the bot commit? | A push with the run's `GITHUB_TOKEN` never triggers a workflow, and the commit only touches `deploy/**`, which is in `paths-ignore`. |
| What would you do next? | Alembic migrations, External Secrets / Sealed Secrets, a staging environment with promotion, backups of the PVC. |

---

# Part B — Detailed test record

- Dates: first run 25 October 2026 (sections 1–3), fixes and final run 29 October 2026 (section 4), ArgoCD 30 October 2026 (section 5), full GitOps loop 1 November 2026 (section 6)
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
| GitOps hand-over (Helm → ArgoCD) | Synced / Healthy in **19 s**, data intact (same PVC, same fingerprint) |
| Drift correction (ArgoCD self-heal) | manual `scale 2 → 5` reverted in **~2 s** |
| Full GitOps loop (push → live, no manual command) | **6 min 48 s – 8 min 09 s** (GitHub run ~3.5 min, ArgoCD detection ~3 min, rollout < 45 s) |

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

## 5. GitOps with ArgoCD (30 October 2026)

GitOps: the GitHub repository is the single source of truth. ArgoCD runs in the
cluster, continuously compares the live namespace with the Helm chart in Git, applies
every new commit and reverts any manual change (drift). Deploying means committing;
rolling back means reverting a commit.

### 5.1 Installation

- **ArgoCD v3.5.6**, official manifests pinned to the tag (images `argocd:v3.5.6`,
  `dex:v2.45.1`, `redis:8.2.3-alpine`), installed with server-side apply (the CRDs are
  too large for a client-side apply). ArgoCD 3.5 is tested on Kubernetes 1.33–1.36.
- 7 pods Running, 0 restarts, **144 MiB** of RAM at rest (`kubectl top`).
- The nodes pulled the 433 MB ArgoCD image from quay.io at 0–270 KB/s; the images were
  pulled once on the host and loaded into both nodes with `k3d image import` (25 s).
- UI: `kubectl port-forward svc/argocd-server -n argocd 8443:443` → `https://localhost:8443`, user `admin`.

### 5.2 Hand-over from Helm to ArgoCD — data kept

`deploy/argocd/leoni-application.yaml`: repository `herchr445/leoni-maintenance`, branch
`main`, path `deploy/helm/leoni`, `values-local.yaml`, namespace `leoni`, automated sync
with `prune` and `selfHeal`, retry with exponential backoff, no cascading finalizer.

Why the data survives the hand-over:

- The PVC `data-leoni-postgres-0`, the Secret `leoni-db` and the namespace carry no
  Helm annotation and no owner, so `helm uninstall` does not delete them.
- A StatefulSet finds its PVC **by name**. The Application pins `releaseName: leoni`,
  so the new StatefulSet is again `leoni-postgres` and reattaches `data-leoni-postgres-0`.
  With another release name (e.g. `leoni-app`) it would have created a new, empty PVC.
- ArgoCD v3.5.6 tracks resources by annotation (`argocd.argoproj.io/tracking-id`): it only
  manages what it applied itself. The Secret and the PVC have no such annotation, so
  `prune` never touches them.

| Step | Result |
|---|---|
| `helm uninstall leoni` | PVC and Secret kept, **same UIDs**; namespace Active |
| `kubectl apply` of the Application (1 s later) | **Synced / Healthy 19 s** after the uninstall, revision `62c6fd9` |
| Data after the sync | **same fingerprint** `85c6824ee32e`, same PVC (the only one in the namespace), 5 work orders |
| Managed by ArgoCD | 8 resources (3 Services, 2 Deployments, StatefulSet, Ingress, NetworkPolicy), all Synced |
| Downtime measured (request every 0.2 s) | **16 s** (45 / 569 requests): `404` while the Ingress was gone, `503` until the new pods were Ready |

The 16 s are the cost of `helm uninstall`: a zero-downtime hand-over would let ArgoCD
adopt the existing resources instead of deleting and recreating them.

### 5.3 Drift correction (self-heal)

Manual drift: `kubectl scale deployment leoni-backend -n leoni --replicas=5`
(Git says 2). Desired replicas polled every 0.5 s:

| Run | Back to 2 replicas after |
|---|---|
| 1 | **2.0 s** |
| 2 | **1.8 s** |
| 3 (third drift in ~30 s) | 11.4 s |

An isolated drift is reverted in **about 2 s**. ArgoCD spaces out repeated self-heals on
the same application with an exponential backoff (2 s, × 3 each time, capped at 300 s —
`controller.self.heal.backoff.*`, defaults), so that it never fights another tool in a
loop; this explains the third run. ArgoCD logs each correction as an automated
"Partial sync … succeeded" (only the drifted resource is re-applied).

## 6. Full GitOps loop: push code → live in the cluster (1 November 2026)

No manual command between `git push` and the change being visible on `http://localhost:8090`.

### 6.1 The chain

1. **GitHub Actions** (on every push to `main` outside `deploy/**` and `docs/**`):
   tests, Ruff, Bandit, SonarCloud analysis with a **blocking Quality Gate** → build both
   images → Trivy report (non-blocking) + **blocking check on fixable CRITICAL
   vulnerabilities** → push to GHCR with the short commit SHA as tag.
2. **Tag bump job** (`update-tags`, the only job with `contents: write`): writes the new tag
   into `deploy/helm/leoni/values-local.yaml` and pushes a commit as `github-actions[bot]`
   (strict `sed` on the two tag lines + guards; retry loop if `main` moved).
   No infinite loop: a push made with the run's `GITHUB_TOKEN` never triggers a workflow,
   and the commit only touches `deploy/**` (`paths-ignore`). It does not trigger the Azure
   pipeline either (`trigger.paths.exclude: deploy`).
3. **ArgoCD** polls the repository (default every 3 minutes), sees the new tags and rolls
   out the new images (rolling update with `preStop` drain).

The gates were proven in real conditions: a first run stopped at "Block on fixable CRITICAL
vulnerabilities (frontend)" (CVE-2026-111497 in `brotli-libs` of the nginx base image);
nothing was published or deployed until the fix (`apk upgrade brotli-libs`, base pinned to
`nginx-unprivileged:1.31.7-alpine3.24`).

### 6.2 End-to-end test — measured timings

Cycle 1: visible text change in `frontend/src/App.jsx` (subtitle + "(test GitOps E2E)").
Cycle 2: `git revert` of that commit. Times from the GitHub API (runs #9 and #10), the bot
commits, ArgoCD's history and a watcher polling `localhost:8090` every 3 s.

| Stage | Cycle 1 (change) | Cycle 2 (revert) |
|---|---|---|
| GitHub job 1: tests, Quality Gate, SonarCloud | 1 min 27 s | 1 min 21 s |
| GitHub job 2: build, blocking Trivy, push to GHCR | 2 min 06 s | 1 min 46 s |
| GitHub job 3: tag bump commit | 8 s | 6 s |
| **Whole GitHub Actions run** | **3 min 50 s** | **3 min 22 s** |
| ArgoCD detection of the bot commit (polling) | 3 min 27 s | 3 min 10 s |
| Rolling update (incl. pulling the new images) | 44 s | 38 s |
| **Push → change visible on `localhost:8090`** | **8 min 09 s** | **6 min 48 s** |

| Cycle | Push | Bot commit | ArgoCD sync | Visible |
|---|---|---|---|---|
| 1 | `13f8de2` 11:56:12 | `6b17878` 11:59:59 | 12:03:29 | 12:04:21 |
| 2 | `a21d620` 12:26:51 | `d5f0fef` 12:30:09 | 12:33:22 | 12:33:39 |

(UTC.) In cycle 2 the new text was served 17 s after the sync started, before the rollout
finished: Traefik sends traffic to each new pod as soon as it is Ready.

The longest stage is ArgoCD's detection (~45 % of the total). It could be shortened by
lowering `timeout.reconciliation` (default 180 s) or with a webhook from GitHub — not
possible here, since GitHub cannot reach a cluster running on a laptop.

The Azure DevOps pipeline stayed green on the same commits (runs 20261101.3 and
20261101.4, CI + Deploy Succeeded), and did not run for the bot commits.

### 6.3 Blank page after a rollout — diagnosed and fixed

After cycle 2, `localhost:8090` stayed blank until a hard reload (Ctrl+Shift+R).

Diagnosis (headers of the running frontend):

- `index.html` had no `Cache-Control`: browsers may reuse it on their own (heuristic cache,
  ~10 % of its age) and request JS files of an older version.
- A missing `/assets/*.js` answered **`200 text/html`** (the SPA fallback served
  `index.html`). The browser refuses to run HTML as a script → blank page.
- During a rolling update, old and new pods serve requests together for a few seconds.
  A browser can get the new `index.html` from a new pod and its JS from an old pod
  → `200 text/html` → **and the browser caches that wrong response**, so every normal
  reload stays blank.

Fix in `frontend/nginx.conf`:

| Path | Before | After |
|---|---|---|
| `index.html`, `/`, SPA routes | no `Cache-Control` | `no-cache` (always revalidated, `304` if unchanged) |
| `/assets/*` (hashed names) | no `Cache-Control` | `public, max-age=31536000, immutable` |
| missing `/assets/*` | `200` + `index.html` | `404` + `no-store` |

Test: temporary namespace with only the frontend (2 replicas, same `preStop`) on a
dedicated host, and a browser simulator applying the browser cache rules (F5 =
revalidate the page, cached sub-resources). 4 browsers reload every 0.5 s before,
during and after each rolling update.

| nginx config | Rollouts | Blank loads during the version overlap | Blank reloads **after** the rollout (poisoned cache) |
|---|---|---|---|
| before | 2 | 1 | **288** (58 + 230; up to 4/4 browsers stuck until a hard reload) |
| after | 2 | 6 (each followed by a working reload) | **0** |

The reported bug (a page that stays blank) is gone. What remains: a browser that reloads
during the ~3 s overlap can get one blank load (its JS requested from an old pod → `404`);
the next reload works. A Traefik sticky cookie was tested to keep each browser on one pod
and **rejected**: browsers pinned to a stopping pod got `502` / no response for up to 14 s
(11 errors). Removing the last transient case would need the previous version's assets to
stay available during a rollout (kept in the new image, or served from shared storage/CDN).

### 6.4 Keeping the two remotes in sync

The bot commits only exist on GitHub. After each code push:

```powershell
git push origin main                # Azure: build + Docker Desktop deployment
git push github main                # GitHub: tests → images → bot tag commit → ArgoCD
# wait for the GitHub run to finish, then:
git pull --ff-only github main      # bring the bot commit locally
git push origin main                # Azure Repos identical (deploy/ only → no Azure run)
```

## 7. State left running

| | |
|---|---|
| Deployment method | **ArgoCD** Application `leoni` (automated, prune, selfHeal), Synced / Healthy, revision `21c643d` (bot commit) |
| Images | `c2b613f` (frontend cache fix; written into `values-local.yaml` by the GitHub Actions bot) |
| Pods | 2 backend, 2 frontend, 1 postgres — all `1/1 Running` (postgres: 1 restart when the k3d nodes restarted with Docker Desktop on 1 November; data intact) |
| Resources (`kubectl top`) | backend ~58 MiB each, frontend ~13 MiB each, postgres ~21 MiB; ArgoCD 144 MiB |
| Data | 5 work orders in PostgreSQL (PVC `data-leoni-postgres-0`) |

Useful commands:

```powershell
kubectl get pods -n leoni
kubectl get application leoni -n argocd          # sync and health status
kubectl port-forward svc/argocd-server -n argocd 8443:443
k3d cluster stop leoni     # free RAM; k3d cluster start leoni to resume (data kept)
```

From now on, changes go through Git: a manual `kubectl` or `helm` change on the
`leoni` namespace is reverted by ArgoCD.

Data safety: uninstalling, upgrading or re-syncing does not delete the PVC (it is
created by the StatefulSet, not by Helm or ArgoCD, and its retention policy is `Retain`).
The data is deleted only by `kubectl delete pvc`, deleting the namespace, or deleting the cluster.
