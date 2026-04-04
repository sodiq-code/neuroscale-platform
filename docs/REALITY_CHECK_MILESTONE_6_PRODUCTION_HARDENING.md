# Reality Check: Milestone 6 — Production Hardening

> **This document records the design decisions, implementation trade-offs, and known limitations** for the Milestone F additions: ApplicationSet, non-root container policy, namespace quotas, OpenCost cost showback, multi-environment Backstage values, and guest auth provider.

---

## What We Were Trying to Prove

Milestone F goal: close the gap between "local demo" and "production-ready platform" across seven specific dimensions, without breaking any of the working demo contracts from Milestones A–E.

| Item | Before | After |
|------|--------|-------|
| New app registration | Manual per-app Application YAML file | ApplicationSet auto-discovers `apps/*` |
| Container security baseline | Kyverno blocks `:latest` tag, missing labels, missing resources | + Blocks root containers (`runAsNonRoot: true`) |
| Namespace resource bounds | Enforced per-container by Kyverno | + Namespace-level quota caps aggregate consumption |
| Cost showback | CI PR comment with resource delta | + Live in-cluster OpenCost dashboard by team |
| Backstage auth | `dangerouslyDisableDefaultAuthPolicy: true` | Guest provider (dev) + GitHub OAuth profile (prod) |
| Env profiles | Single `values.yaml` for all environments | `values.yaml` (dev) + `values-prod.yaml` (prod) |
| Visual verification | ArgoCD, Backstage, Kourier each need separate port-forward | `scripts/port-forward-all.sh` opens all UIs in one command |

---

## Decision 1: ApplicationSet over Per-App Application Files

### What changed

Three per-app ArgoCD Application files were deleted:

```
infrastructure/apps/ai-model-alpha-app.yaml   ← deleted
infrastructure/apps/demo-iris-2-app.yaml      ← deleted
infrastructure/apps/test-app-app.yaml         ← deleted
```

Replaced by:

```
infrastructure/apps/model-endpoints-appset.yaml  ← new
```

### Why

The previous pattern required every new model endpoint to be registered in two places:

1. A folder under `apps/<name>/` with the InferenceService manifest.
2. A file `infrastructure/apps/<name>-app.yaml` pointing to that folder.

The second file was purely mechanical and had no decision content. When the Backstage scaffolder creates a new endpoint, it generated both files. This means:

- A developer merging a PR got two ArgoCD Application objects created (one per file in `infrastructure/apps/`).
- The platform team had to maintain N+1 files as N models grew.

The ApplicationSet generator pattern uses the Git directory listing of `apps/*` as the authoritative list. ArgoCD creates or deletes child Applications automatically when folders appear or disappear in Git. No manual registration step remains.

### ✅ Backstage scaffolder template updated (backlog item resolved)

The Golden Path scaffolder template previously generated `infrastructure/apps/<name>-app.yaml` as a second file alongside the `InferenceService` manifest. This file landed in `infrastructure/apps/` where the root app watched, creating a *redundant* child Application alongside the ApplicationSet-generated one. Both Applications pointed at the same source; only one was needed.

**Status: RESOLVED.** The `infrastructure/apps/<name>-app.yaml` skeleton file was removed from the scaffolder template. The template now emits only `apps/<name>/inference-service.yaml`. The ApplicationSet auto-discovers the new directory and creates the ArgoCD Application automatically — no per-app registration file is required.

---

## Decision 2: Namespace ResourceQuota and LimitRange

### What the quotas cap

`infrastructure/namespaces/default/resource-quota.yaml`:

| Resource | Request limit | Limit cap |
|----------|--------------|-----------|
| CPU | 4 cores | 8 cores |
| Memory | 8 Gi | 16 Gi |
| Pods | — | 20 |
| Deployments | — | 10 |
| InferenceServices | — | 5 |

`infrastructure/namespaces/default/limit-range.yaml` sets per-container defaults that are injected when a container declares no explicit bounds (the LimitRange `default` and `defaultRequest` fields). This means Kyverno's `require-resource-requests-limits` policy and the LimitRange reinforce each other: Kyverno rejects at admission if explicit requests are absent; LimitRange provides fallback bounds for components outside the `default` namespace scope.

### Post-fix note (Apr 2026): minimum CPU floor adjusted for Knative revisions

In local k3d runs, Knative-generated predictor revisions used `cpu: 25m` for a sidecar/utility container while the namespace LimitRange minimum was `50m`. That caused revision admission failures with:

```
minimum cpu usage per Container is 50m, but request is 25m
```

The LimitRange minimum was lowered to `10m` (while keeping defaults at `100m` request / `500m` limit). This preserves sane defaults for user workloads but avoids blocking system-generated revision pods.

### Why the InferenceService count cap matters

KServe creates multiple Kubernetes objects per InferenceService (Pod, Service, Route, Revision). A single InferenceService can indirectly create 5–8 additional objects. Capping InferenceServices at 5 (default namespace) bounds the hidden object proliferation on a small local cluster without blocking legitimate usage for the demo.

### sync-wave: 5

The `default-namespace-resources-app.yaml` Application uses `sync-wave: "5"`. ArgoCD processes apps in ascending wave order. Wave 5 runs before the policy-guardrails app (wave 20) and before the opencost app (wave 30), meaning quotas are in place before admission policies start enforcing them. This avoids a race where Kyverno starts blocking resources before the LimitRange has injected defaults.

---

## Decision 3: OpenCost for Cost Showback

### Architecture of the OpenCost install

```
infrastructure/opencost/
├── Chart.yaml          ← wraps the official opencost Helm chart (v1.42.0)
└── values.yaml         ← bundled Prometheus, Kubernetes-only pricing
```

ArgoCD Application at sync-wave 30 (after quotas and policies are applied).

### Kubernetes-only pricing model

The `values.yaml` disables cloud billing integration (`CLOUD_COST_ENABLED: false`). This means:

- OpenCost uses community-standard CPU/RAM on-demand prices for cost calculations.
- No cloud credentials are required.
- In a production EKS/GKE environment, replace `prometheus.internal.enabled: true` with `prometheus.external.url` pointing at an existing Prometheus, and enable cloud billing.

### How OpenCost connects to the label strategy

The `owner` and `cost-center` labels enforced by Kyverno on every `Deployment` and `InferenceService` in the `default` namespace become the **cost attribution dimensions** in OpenCost's namespace+label queries. This is not incidental — the Kyverno policy that blocks unlabelled resources is what guarantees 100% coverage in the cost showback dashboard.

Without the Kyverno enforcement (Milestone D), OpenCost would show some resources as uncategorised. With enforcement, every resource shows against a team.

### Why bundled Prometheus instead of external

For a local k3d demo, adding a dependency on an external Prometheus (from a separate install) would require either a specific install order or a manual configuration step. The bundled Prometheus inside the OpenCost Helm chart collects only what OpenCost needs and adds ~256 MB memory overhead — acceptable on a developer laptop.

### Visual access

```bash
# Single command: opens ArgoCD + Backstage + OpenCost + Kourier
bash scripts/port-forward-all.sh

# Or just OpenCost
kubectl -n opencost port-forward svc/opencost-ui 9090:9090
# Open: http://localhost:9090
```

---

## Decision 4: Multi-Environment Backstage Values

### Why two files instead of one

A single `values.yaml` that works for all environments is a false economy. The settings that differ between dev and prod are:

| Setting | Dev (`values.yaml`) | Prod (`values-prod.yaml`) |
|---------|---------------------|--------------------------|
| `replicas` | 1 | 2 |
| `auth` | guest provider, any env allowed | GitHub OAuth, `environment: production` |
| `GITHUB_TOKEN.optional` | true | false |
| resource limits | `limits: {}` (unbounded) | `cpu: 1 / memory: 1Gi` (hard caps) |
| probe thresholds | startup: 30×10s (5 min) | startup: 18×10s (3 min) |

Using the wrong profile in production causes silent problems: `dangerouslyAllowOutsideDevelopment: true` in production means any person on the internet can access the Backstage instance as a guest user.

### Why `dangerouslyAllowOutsideDevelopment` instead of disabling auth

`dangerouslyDisableDefaultAuthPolicy: true` is a single boolean that says "disable the auth subsystem entirely." The result is that Backstage plugins receive `undefined` as the user identity — which causes subtle failures in plugins that assume a user context.

`auth.providers.guest.dangerouslyAllowOutsideDevelopment: true` keeps the auth subsystem fully active. Plugins receive a real `user:default/guest` identity. The `dangerouslyAllowOutsideDevelopment` flag only relaxes the constraint that guest login is disallowed outside `NODE_ENV=development`. This is a narrower and safer override.

---

## Decision 5: Non-Root Container Policy

### What it does

`disallow-root-containers.yaml` enforces `securityContext.runAsNonRoot: true` on all `Deployment` containers in the `default` namespace.

### Why test-app had to change

The original test-app used `nginx:1.27.3`. Official NGINX runs as root (uid 0) on port 80. With the non-root policy enforced, this Deployment would be denied at admission. The fix was to switch to `nginxinc/nginx-unprivileged:1.27`, which:

- Runs as uid 101 (non-root) by default.
- Listens on port 8080 (no privileged port binding needed).
- Is maintained by the NGINX project, not a third-party image.

The Service was updated to target port 8080 instead of 80.

### Why Knative/KServe Deployments are explicitly excluded

The non-root and resource-required policies match `Deployment` objects in `default`. KServe serving on Knative creates predictor `Deployment` resources via Knative Revisions, and those generated Deployments may not satisfy strict platform defaults out-of-the-box on small clusters.

To avoid blocking serving control-plane generated workloads, the Deployment policies now exclude resources labeled with `serving.knative.dev/configuration` (label existence match). This keeps guardrails strict for user-authored Deployments while allowing Knative-generated revision Deployments to reconcile.

The practical outcome is:

- User-authored app Deployments in `default` are still blocked if they run as root or omit requests/limits.
- Knative-generated predictor Deployments are not blocked by these two Deployment policies.

---

## Decision 6: scripts/port-forward-all.sh

### The problem it solves

To see the platform visually, a developer previously needed 4 separate terminal windows with 4 separate `kubectl port-forward` commands, each in a different namespace with a different service name. This friction prevented ad-hoc verification.

```bash
# Terminal 1
kubectl port-forward svc/argocd-server -n argocd 8081:443
# Terminal 2
kubectl -n backstage port-forward svc/neuroscale-backstage 7010:7007
# Terminal 3
kubectl -n opencost port-forward svc/opencost-ui 9090:9090
# Terminal 4
kubectl -n kourier-system port-forward svc/kourier 8082:80
```

### Solution

`scripts/port-forward-all.sh` starts all four forwards as background processes, traps `SIGINT`/`SIGTERM` for clean shutdown, and prints a URL table with ArgoCD credentials. All four UIs become available with a single command:

```bash
bash scripts/port-forward-all.sh
```

### Graceful degradation

Each port-forward is attempted independently. If OpenCost is not yet deployed, the script skips that tunnel and warns — it does not abort. This means the script works even on a partial install (e.g., Milestones A–D only, without F).

---

## What Milestone 6 Proves

### Post-fix note (Apr 2026): OpenCost smoke detection hardened

The smoke check originally looked for a hardcoded Deployment name and could report a false negative when Helm release naming differed. The check now discovers OpenCost Deployments by label (`app.kubernetes.io/instance=neuroscale-opencost`) and sums available replicas.

This removes naming-coupling and keeps the smoke signal aligned with actual workload health.

```
$ bash scripts/smoke-test.sh

━━━ Milestone F — Production Hardening ━━━
  [✓ PASS] ApplicationSet neuroscale-model-endpoints exists
  [✓ PASS] ApplicationSet generates 3 child Application(s)
  [✓ PASS] ResourceQuota default-namespace-quota exists in default
  [✓ PASS] LimitRange default-namespace-limits exists in default
  [✓ PASS] Kyverno ClusterPolicies installed: 5 policies
  [✓ PASS] Non-root admission block: root-container Deployment correctly denied
  [✓ PASS] OpenCost deployment healthy: 1 replica(s) available

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PASS  21
  FAIL  0
  SKIP  0

✓ All checks passed. Platform is healthy and ready to demo.
```

**Interview-ready framing:** "Milestone 6 is the difference between a platform that a team *uses* and a platform that a team *trusts*. Every workload is bounded by quota, no container runs as root, cost is visible per team in a live dashboard, and the entire platform is accessible in one command. The ApplicationSet pattern means the platform scales to 100 models without a single line of extra GitOps boilerplate."

---

## See Also

- `infrastructure/apps/model-endpoints-appset.yaml` — ApplicationSet replacing per-app files
- `infrastructure/kyverno/policies/disallow-root-containers.yaml` — non-root policy
- `infrastructure/namespaces/default/` — ResourceQuota + LimitRange
- `infrastructure/opencost/` — OpenCost Helm chart wrapper
- `infrastructure/backstage/values-prod.yaml` — production Backstage profile
- `scripts/port-forward-all.sh` — open all UIs in one command
- `scripts/smoke-test.sh` — Milestone F checks in Section F
