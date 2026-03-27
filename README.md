# NeuroScale Platform

> **Executive Summary:** NeuroScale is a self-service AI inference platform on Kubernetes. A developer fills in a Backstage form, the platform creates a pull request, ArgoCD deploys it, and a production-grade KServe inference endpoint is live — with cost attribution, drift control, and policy guardrails enforced automatically at every stage.

---

## Table of Contents

1. [Why NeuroScale Exists: Addressing 2026 ML Infrastructure Pain Signals](#1-why-neuroscale-exists-addressing-2026-ml-infrastructure-pain-signals)
2. [Architecture: Control Plane and Data Plane](#2-architecture-control-plane-and-data-plane)
3. [System Flow: How Everything Connects](#3-system-flow-how-everything-connects)
   - [GitOps: How Deployments Are Triggered](#31-gitops-how-deployments-are-triggered)
   - [Backstage: How Services Are Cataloged and Scaffolded](#32-backstage-how-services-are-cataloged-and-scaffolded)
   - [KServe: How Inference Is Handled](#33-kserve-how-inference-is-handled)
4. [Repository Map](#4-repository-map)
5. [Milestone Status](#5-milestone-status)
6. [Quickstart: Running the Demo Locally](#6-quickstart-running-the-demo-locally)
7. [Reality Check Documentation](#7-reality-check-documentation)
8. [Guardrails: What Gets Blocked and Why](#8-guardrails-what-gets-blocked-and-why)
9. [Operational Runbook: ArgoCD Sync Recovery, KServe Restart, and Backstage Token Refresh](#9-operational-runbook-argocd-sync-recovery-kserve-restart-and-backstage-token-refresh)
10. [Interview Defense: Mapping Platform Decisions to Production Engineering Signals](#10-interview-defense-mapping-platform-decisions-to-production-engineering-signals)

---

## 1. Why NeuroScale Exists: Addressing 2026 ML Infrastructure Pain Signals

The 2026 platform engineering pain signals this repo directly addresses:

| Pain | Industry Signal | NeuroScale Answer |
|------|----------------|-------------------|
| Complexity / cognitive load | Developers shouldn't need Kubernetes expertise to deploy a model | Backstage Golden Path template — one form, one PR |
| Reliability / drift | Manual cluster changes break overnight | ArgoCD GitOps — Git is the source of truth; drift is auto-corrected |
| Governance & security | Unsafe configs reach production | Kyverno admission policies + CI policy simulation |
| Cost waste | No resource bounds = unbounded spend | Required requests/limits + `owner`/`cost-center` labels enforced before merge |

---

## 2. Architecture: Control Plane and Data Plane

```
+--------------------------------- CONTROL PLANE ---------------------------------+
|                                                                                  |
|  Developer                                                                       |
|     |                                                                            |
|     v                                                                            |
|  Backstage (Golden Path UI)                                                      |
|  - Template form (name, modelFormat, storageUri)                                 |
|  - Scaffolder: opens PR to GitHub with two files                                 |
|      apps/<name>/inference-service.yaml                                          |
|      infrastructure/apps/<name>-app.yaml                                         |
|                                                                                  |
|  GitHub Pull Request                                                             |
|  - CI: kubeconform schema validation                                             |
|  - CI: Kyverno policy simulation against rendered manifests                      |
|  - PR blocked if labels, resources, or image tag rules are violated              |
|                                                                                  |
|  ArgoCD (GitOps reconciler)                                                      |
|  - Root app-of-apps: bootstrap/root-app.yaml                                    |
|  - Watches: infrastructure/apps/ for child Application manifests                 |
|  - On merge: detects new <name>-app.yaml -> creates child Application            |
|  - Syncs apps/<name>/inference-service.yaml to cluster                           |
|  - Self-heals drift: any manual kubectl change is reverted automatically         |
|                                                                                  |
|  Kyverno (Admission Control)                                                     |
|  - Blocks InferenceService without owner + cost-center labels                    |
|  - Blocks Deployment without CPU/memory requests + limits                        |
|  - Blocks :latest image tags on Deployments                                      |
|                                                                                  |
+----------------------------------------------------------------------------------+

+---------------------------------- DATA PLANE -----------------------------------+
|                                                                                  |
|  KServe Controller                                                               |
|  - Watches InferenceService CRD                                                  |
|  - Creates Knative Service + Revision + Route                                    |
|                                                                                  |
|  Knative Serving                                                                 |
|  - Manages pod lifecycle for predictor containers                                |
|  - Routes traffic by Host header via Kourier                                     |
|                                                                                  |
|  Kourier (Ingress Gateway)                                                       |
|  - Lightweight Envoy-based ingress for Knative                                   |
|  - Accepts inference requests on port 80                                         |
|                                                                                  |
|  Predictor Pod (sklearn, xgboost, etc.)                                          |
|  - Runs ClusterServingRuntime (infrastructure/kserve/sklearn-runtime.yaml)       |
|  - Serves /v1/models/<name>:predict                                              |
|                                                                                  |
+----------------------------------------------------------------------------------+
```

---

## 3. System Flow: How Everything Connects

### 3.1 GitOps: How Deployments Are Triggered

GitOps in NeuroScale is implemented with **ArgoCD app-of-apps**. There is one root Application (`bootstrap/root-app.yaml`) that watches `infrastructure/apps/`. Every file in that directory is itself an ArgoCD Application targeting a specific folder in the repo.

**Trigger chain:**

```
Git commit to main
       |
       v
ArgoCD root app polls infrastructure/apps/
       |
       +-> Detects new <name>-app.yaml
       |         |
       |         v
       |   Creates child Application object in-cluster
       |         |
       |         v
       |   Child app syncs apps/<name>/inference-service.yaml
       |
       +-> Self-heal loop: every ~3 minutes, desired state in Git
            is compared to live state in cluster.
            Any manual drift (kubectl delete, kubectl edit) is reverted.
```

**Key design decision — why app-of-apps instead of a monolithic sync:**

- Each child app has an independent sync window, rollback boundary, and health check.
- A broken `InferenceService` YAML does not block unrelated platform components from syncing.
- Blast radius is explicitly bounded per service.

**Automated sync settings** (from `bootstrap/root-app.yaml`):

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

`selfHeal: true` means ArgoCD continuously reconciles. `prune: true` means resources removed from Git are removed from the cluster.

### 3.2 Backstage: How Services Are Cataloged and Scaffolded

Backstage serves two functions in NeuroScale:

**a) Service Catalog** — every deployed inference service is a cataloged Component with ownership metadata. The `owner` and `cost-center` labels required by Kyverno feed directly into catalog attribution.

**b) Golden Path Scaffolder** — the `KServe model endpoint` template at `backstage/templates/model-endpoint/template.yaml` generates the two files required by the GitOps pipeline:

```
User fills form in Backstage
        |
        v
Scaffolder publishes PR to GitHub containing:
  apps/<name>/inference-service.yaml          <- KServe manifest, labels, resources
  infrastructure/apps/<name>-app.yaml         <- ArgoCD Application pointing to apps/<name>
        |
        v
CI runs on the PR (kubeconform + Kyverno simulation)
        |
        v
Human reviews and merges PR
        |
        v
ArgoCD detects new child app file -> deploys -> InferenceService becomes Ready
```

**The critical non-obvious piece:** Backstage is *not* the deployment engine. It is the UX that generates Git artifacts. ArgoCD is the deployment engine. This separation means Backstage can be down without affecting running inference endpoints.

### 3.3 KServe: How Inference Is Handled

KServe operates in **serverless mode** (Knative-based) in this platform. The request path for a deployed `InferenceService` named `demo-iris-2` is:

```
curl (with Host header)
       |
       v
Kourier (svc/kourier in namespace kourier-system, port 80)
       |  routes by Host: demo-iris-2-predictor.default.<domain>
       v
Knative Route -> Knative Revision
       |
       v
Predictor Pod (running sklearn-runtime image)
       |  port 8080
       v
/v1/models/demo-iris-2:predict -> {"predictions":[1,1]}
```

**Why Kourier instead of Istio:** The cluster runs on local k3d with constrained RAM. Istio adds ~1 GB memory overhead. Kourier is a minimal Envoy-based gateway that Knative supports natively and costs ~100 MB. The ingress config patch at `infrastructure/serving-stack/patches/inferenceservice-config-ingress.yaml` sets `disableIstioVirtualHost: true` to signal this choice to KServe.

**ClusterServingRuntime:** `infrastructure/kserve/sklearn-runtime.yaml` defines a reusable runtime that all sklearn-based `InferenceService` objects reference. This separates *how to serve* from *what to serve*, allowing the runtime image to be patched in one place.

---

## 4. Repository Map

```
neuroscale-platform/
|-- bootstrap/
|   +-- root-app.yaml                    # GitOps entrypoint: seeds ArgoCD app-of-apps
|
|-- infrastructure/
|   |-- apps/                            # ArgoCD child Application manifests
|   |   |-- backstage-app.yaml
|   |   |-- serving-stack-app.yaml
|   |   |-- kserve-runtimes-app.yaml
|   |   |-- policy-guardrails-app.yaml
|   |   |-- ai-model-alpha-app.yaml
|   |   |-- demo-iris-2-app.yaml
|   |   +-- test-app-app.yaml
|   |-- backstage/
|   |   |-- Chart.yaml                   # Helm chart wrapper for Backstage
|   |   +-- values.yaml                  # Probe tuning, resource bounds, config injection
|   |-- kserve/
|   |   +-- sklearn-runtime.yaml         # ClusterServingRuntime (sklearn)
|   |-- kyverno/
|   |   |-- kyverno-install-v1.12.5.yaml
|   |   +-- policies/                    # Admission + audit policies
|   |-- serving-stack/
|   |   |-- kustomization.yaml           # cert-manager + Knative + Kourier + KServe install
|   |   +-- patches/                     # Istio->Kourier config, kube-rbac-proxy removal
|   +-- INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md
|
|-- apps/
|   |-- test-app/deployment.yaml         # Simple workload for drift self-heal demo
|   |-- ai-model-alpha/                  # First inference service (Milestone B)
|   +-- demo-iris-2/                     # Golden Path output (Milestone C)
|
|-- backstage/
|   +-- templates/model-endpoint/        # Scaffolder template (Golden Path)
|
|-- .github/workflows/
|   +-- guardrails-checks.yaml           # CI: kubeconform + Kyverno policy simulation
|
|-- docs/
|   |-- PROJECT_MEMORY.md
|   |-- LEARNING_STRATEGY_AGREEMENT.md
|   |-- WEEK_1_LEARNING_REVIEW.md
|   |-- WEEK_2_LEARNING_REVIEW.md
|   |-- WEEK_3_GOLDEN_PATH_CONTRACT.md
|   |-- HANDOFF_PROMPT.md
|   |-- REALITY_CHECK_MILESTONE_1_GITOPS_SPINE.md
|   |-- REALITY_CHECK_MILESTONE_2_KSERVE_SERVING.md
|   |-- REALITY_CHECK_MILESTONE_3_GOLDEN_PATH.md
|   +-- REALITY_CHECK_MILESTONE_4_GUARDRAILS.md
|
|-- plan-neuroScale.prompt.md
+-- README.md
```

---

## 5. Milestone Status

| Milestone | Description | Status |
|-----------|-------------|--------|
| **A** | GitOps spine: ArgoCD manages infra + apps; drift self-heal proven | Done |
| **B** | AI serving baseline: GitOps-managed KServe install + one endpoint verified | Done |
| **C** | Golden Path: Backstage creates PR -> merge -> ArgoCD deploys -> InferenceService Ready | Done |
| **D** | Guardrails: Kyverno admission + PR-time CI policy simulation baseline | Done |

---

## 6. Quickstart: Running the Demo Locally

### Prerequisites

- Docker Desktop (or Rancher Desktop)
- `k3d` installed
- `kubectl` installed
- `helm` installed

### Start the cluster

```bash
k3d cluster start neuroscale
```

### Morning health gate (run every session)

```bash
kubectl get nodes
kubectl -n argocd get applications.argoproj.io
kubectl -n kserve get deploy,pods
kubectl -n default get inferenceservices.serving.kserve.io
```

### Open required tunnels

```bash
# Terminal 1 -- ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8081:443

# Terminal 2 -- Inference gateway (Kourier)
kubectl -n kourier-system port-forward svc/kourier 8082:80

# Terminal 3 -- Backstage portal
kubectl -n backstage port-forward svc/neuroscale-backstage 7010:7007
```

### Demo: GitOps drift self-heal (Milestone A)

```bash
# Confirm workload exists
kubectl get deploy nginx-test -n default

# Create intentional drift
kubectl delete deploy nginx-test -n default

# Wait and verify self-heal
sleep 20
kubectl get deploy nginx-test -n default
```

### Demo: Inference request (Milestone B / C)

```bash
# Get predictor pod name
kubectl -n default get pods -l serving.knative.dev/revision=demo-iris-2-predictor-00001

# Port-forward to predictor runtime directly (deterministic local proof)
kubectl -n default port-forward pod/<predictor-pod-name> 18080:8080

# Send prediction
curl -sS -H "Content-Type: application/json" \
  -d '{"instances":[[6.8,2.8,4.8,1.4],[6.0,3.4,4.5,1.6]]}' \
  http://127.0.0.1:18080/v1/models/demo-iris-2:predict
# Expected: {"predictions":[1,1]}
```

### Demo: Policy block (Milestone D)

```bash
# Try to apply a non-compliant InferenceService (missing owner/cost-center labels)
kubectl apply -f - <<EOF
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: bad-model
  namespace: default
spec:
  predictor:
    sklearn:
      storageUri: gs://kfserving-examples/models/sklearn/1.0/model
EOF
# Expected: admission webhook denial from Kyverno
```

---

## 7. Reality Check Documentation

**This platform was not built on the happy path.** Every milestone hit real failures. The docs below document what broke, the exact terminal output, the root cause, and the business impact.

| Milestone | Reality Check Document | Key Failures Documented |
|-----------|------------------------|-------------------------|
| A — GitOps Spine | [docs/REALITY_CHECK_MILESTONE_1_GITOPS_SPINE.md](docs/REALITY_CHECK_MILESTONE_1_GITOPS_SPINE.md) | ArgoCD repo-server `connection refused`; Argo `Unknown` comparison state; app stuck not syncing |
| B — KServe Serving | [docs/REALITY_CHECK_MILESTONE_2_KSERVE_SERVING.md](docs/REALITY_CHECK_MILESTONE_2_KSERVE_SERVING.md) | Istio vs Kourier ingress mismatch; `kube-rbac-proxy` ImagePullBackOff; Knative CRD rendering conflict |
| C — Golden Path | [docs/REALITY_CHECK_MILESTONE_3_GOLDEN_PATH.md](docs/REALITY_CHECK_MILESTONE_3_GOLDEN_PATH.md) | Backstage CrashLoopBackOff (Helm values mis-nesting); blank `/create/actions` (401 on scaffolder); PR merged but app stayed OutOfSync |
| D — Guardrails | [docs/REALITY_CHECK_MILESTONE_4_GUARDRAILS.md](docs/REALITY_CHECK_MILESTONE_4_GUARDRAILS.md) | InferenceService CRD removed by patch; Kyverno label name mismatch; CI policy simulation environment drift |

Full incident postmortem for the Backstage CrashLoopBackOff: [infrastructure/INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md](infrastructure/INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md)

---

## 8. Guardrails: What Gets Blocked and Why

### Admission-time enforcement (Kyverno)

| Policy | What It Blocks | Business Reason |
|--------|---------------|-----------------|
| `require-standard-labels-inferenceservice` | InferenceService without `owner` + `cost-center` labels | Cost attribution is impossible without ownership metadata |
| `require-resource-requests-limits` | Deployment without CPU/memory requests and limits | Unbounded resources cause node contention and unpredictable cost |
| `disallow-latest-image-tag` | Deployment with `:latest` image | Non-reproducible rollouts; breaks rollback guarantees |

### PR-time enforcement (CI)

| Check | Tool | What It Catches |
|-------|------|----------------|
| Schema validation | `kubeconform` | Malformed YAML, wrong API versions, missing required fields |
| Policy simulation | `kyverno-cli apply` | Policy violations against actual rendered manifests before merge |
| Helm rendering | `helm template` + `render_backstage.sh` | Helm values hierarchy bugs (the exact failure class from the Backstage RCA) |

---

## 9. Operational Runbook: ArgoCD Sync Recovery, KServe Restart, and Backstage Token Refresh

See `docs/WEEK_3_GOLDEN_PATH_CONTRACT.md` for the full runbook.

**Common recovery commands:**

```bash
# Restart ArgoCD repo-server (most common ArgoCD instability fix)
kubectl -n argocd rollout restart deploy/argocd-repo-server
kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=120s

# Refresh a stuck ArgoCD application
kubectl -n argocd patch application <app-name> \
  --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'

# Check KServe controller health
kubectl -n kserve get deploy kserve-controller-manager
kubectl -n kserve describe deploy kserve-controller-manager

# Refresh Backstage GitHub token
read -s GITHUB_TOKEN
kubectl -n backstage create secret generic neuroscale-backstage-secrets \
  --from-literal=GITHUB_TOKEN="$GITHUB_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n backstage rollout restart deploy/neuroscale-backstage
```

---

## 10. Interview Defense: Mapping Platform Decisions to Production Engineering Signals

| Question | Where to Point |
|----------|---------------|
| "Walk me through the GitOps flow" | Section 3.1 + `bootstrap/root-app.yaml` |
| "How does Backstage trigger a deployment?" | Section 3.2 + `backstage/templates/model-endpoint/template.yaml` |
| "How does KServe handle a request?" | Section 3.3 + `infrastructure/kserve/sklearn-runtime.yaml` |
| "How do you prevent bad configs from reaching prod?" | Section 8 + `infrastructure/kyverno/policies/` |
| "Show me a real incident you've debugged" | `infrastructure/INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md` |
| "What failed and what did you learn?" | `docs/REALITY_CHECK_MILESTONE_*.md` |
| "How does cost attribution work?" | Kyverno `require-standard-labels` policy + `cost-center` label requirement |
| "Why Kourier instead of Istio?" | Section 3.3 + `docs/REALITY_CHECK_MILESTONE_2_KSERVE_SERVING.md` |

---

> **Note:** This repo is optimized for local k3d demos. Production parity additions (Ingress TLS, scale-to-zero tuning, multi-namespace isolation, Terraform cost proxy) are documented as the post-Week-4 backlog in `plan-neuroScale.prompt.md`.
