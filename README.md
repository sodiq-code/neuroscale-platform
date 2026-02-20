# NeuroScale Platform

NeuroScale is a self-service AI inference platform on Kubernetes: developers ship model endpoints through a Golden Path, while the platform enforces drift control (GitOps), guardrails (policy-as-code), and cost attribution primitives by default.

## Why this exists (industry pains it targets)

- **Complexity / cognitive load:** developers shouldn’t need to be Kubernetes experts to deploy a model.
- **Reliability / drift:** the cluster should continuously converge to the Git-defined desired state.
- **Governance & security:** prevent unsafe deployments with enforceable guardrails.
- **Cost control:** require attribution + bounded resource usage before changes land.

## Architecture (high level)

- **Control plane:** ArgoCD (GitOps), Backstage (Golden Path UI), CI (render/validate), Kyverno/OPA (policy).
- **Data plane:** KServe model inference endpoints.

## Repository map

- GitOps bootstrap entrypoint: `bootstrap/root-app.yaml`
- Platform components (GitOps-managed): `infrastructure/`
	- Backstage Argo app: `infrastructure/apps/backstage-app.yaml`
	- Test app Argo app: `infrastructure/apps/test-app-app.yaml`
	- Serving stack Argo app: `infrastructure/apps/serving-stack-app.yaml`
	- KServe runtimes Argo app: `infrastructure/apps/kserve-runtimes-app.yaml`
	- Example inference app Argo app: `infrastructure/apps/ai-model-alpha-app.yaml`
	- Backstage Helm wrapper: `infrastructure/backstage/`
	- KServe runtime (example): `infrastructure/kserve/sklearn-runtime.yaml`
- Workloads/apps deployed via GitOps: `apps/`
	- Test workload: `apps/test-app/deployment.yaml`
	- Example inference service: `apps/ai-model-alpha/inference-service.yaml`
- Execution plan and interview script (internal): `plan-neuroScale.prompt.md`

## Status (milestones)

- ✅ **Milestone A — GitOps spine (drift control proven)**
- ✅ **Milestone B — AI serving baseline (KServe install GitOps-managed + one endpoint verified)**
- ⏳ **Milestone C — Golden Path (Backstage creates PR → merge → Argo deploy)**
- ⏳ **Milestone D — Guardrails (CI + admission policies block unsafe changes)**

## Demo: Milestone A (GitOps drift self-heal)

This demo proves the core GitOps claim: **Git is the source of truth** and drift is corrected automatically.

### What you should observe

1. ArgoCD shows the `test-app` Application is **Synced** and **Healthy**.
2. If you manually delete the `nginx-test` Deployment, ArgoCD recreates it.

### Commands (cluster must be running)

```bash
# Confirm the ArgoCD Application exists
kubectl get applications -n argocd

# Confirm the workload exists
kubectl get deploy nginx-test -n default -o wide

# Create intentional drift
kubectl delete deploy nginx-test -n default

# Wait briefly, then verify Argo self-healed
sleep 20
kubectl get deploy nginx-test -n default -o wide
kubectl rollout status deploy/nginx-test -n default --timeout=120s
```

### Evidence to capture

- Screenshot: ArgoCD Applications list (showing `neuroscale-infrastructure` + `test-app` as Synced/Healthy)
- Screenshot: terminal output showing delete → recreated (self-heal)
- Link to the GitOps app definition: `infrastructure/apps/test-app-app.yaml`

## Demo: Milestone B (one inference request succeeds)

This demo proves the AI-serving data plane works end-to-end: **KServe + Knative Serving + Kourier**.

### What you should observe

1. The `sklearn-iris` `InferenceService` is **Ready=True**.
2. A prediction request returns a JSON response (e.g. `{"predictions":[...]}`).

### Commands

```bash
# Confirm the InferenceService is Ready
kubectl -n default get inferenceservice sklearn-iris

# Port-forward the Kourier gateway (use a high local port to avoid conflicts)
kubectl -n kourier-system port-forward svc/kourier 18080:80

# In a second terminal: send a request through Kourier.
# NOTE: Knative routes by Host header; this must match the Knative Service URL host.
curl -sS \
	-H 'Host: sklearn-iris-predictor.default.127.0.0.1.sslip.io' \
	-H 'Content-Type: application/json' \
	-d '{"instances":[[5.1,3.5,1.4,0.2],[6.2,3.4,5.4,2.3]]}' \
	http://127.0.0.1:18080/v1/models/sklearn-iris:predict
```

## Notes

- This repo is optimized for local k3d demos first; production parity components (ingress/TLS, scale-to-zero) come after the core demo loop is stable.
- The week-by-week execution plan and definitions of done live in `plan-neuroScale.prompt.md`.
