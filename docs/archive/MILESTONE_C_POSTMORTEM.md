# Week 3 — Backstage Golden Path (Contract + Troubleshooting + RCA)

This file is the complete Week 3 implementation record for NeuroScale. It includes:
- the target contract,
- the final working architecture,
- the full incident timeline,
- root cause and impact for each failure,
- exact remediations,
- prevention and hardening actions.

## Week 3 Objective
Provide a Golden Path where a developer uses Backstage to generate a PR for a new KServe endpoint, merges the PR, and gets an automatically deployed and ready `InferenceService` through ArgoCD.

## Final Outcome
Week 3 objective is achieved.
- Backstage template runs successfully and opens PRs.
- PR merge creates a new Argo child app.
- Argo deploys the new model endpoint.
- `InferenceService/demo-iris-2` is `Ready=True`.
- Prediction call succeeds (validated by direct pod/service path in-cluster).

## Golden Path Contract (Inputs -> Outputs)
### Inputs (Backstage form)
Template: `KServe model endpoint`
- `name` (required): lowercase DNS label (example: `my-model`)
- `modelFormat` (default: `sklearn`)
- `storageUri` (default: `gs://kfserving-examples/models/sklearn/1.0/model`)

### Outputs (GitOps artifacts)
Backstage opens a PR against `main` with exactly:
- `apps/<name>/inference-service.yaml`
  - `InferenceService` named `<name>` in namespace `default`

Note: the earlier implementation also generated `infrastructure/apps/<name>-app.yaml`
(an ArgoCD `Application` manifest). That file was removed in Milestone F when the
`neuroscale-model-endpoints` ApplicationSet was introduced. The ApplicationSet
auto-discovers every directory under `apps/` and creates the ArgoCD Application
automatically — no per-app registration file is needed.

### Merge behavior
After merge:
- `neuroscale-model-endpoints` ApplicationSet detects new `apps/<name>/` directory
- ApplicationSet creates a child ArgoCD `Application` for `<name>` automatically
- Child app syncs `apps/<name>/inference-service.yaml` to the cluster
- KServe controllers reconcile and serve the endpoint

## Security and Access Model
- No secrets committed to Git.
- Backstage GitHub token comes from Kubernetes Secret `neuroscale-backstage-secrets`.
- Backstage config uses `integrations.github[*].token: ${GITHUB_TOKEN}`.
- Branch protection is enabled for `main` (PR flow enforced), but admin bypass exists; this should be tightened.

## Implementation Timeline and Technical Incidents

### 1) Backstage template not visible in catalog
Symptoms:
- Template entity was rejected.
- Backstage showed "kind not allowed" style behavior.

Cause:
- Catalog location did not explicitly allow `Template` kind for that URL source.

Effect:
- Golden Path template not discoverable in UI.

Fix:
- Added catalog location rule:
  - `catalog.locations[].rules: - allow: [Template]`

Validation:
- Template became visible and runnable in `/create`.

### 2) `/create/actions` loaded as blank page (phase 1)
Symptoms:
- Route returned HTTP 200 but page appeared empty.

Cause:
- Backend endpoint `/api/scaffolder/v2/actions` returned `401 Missing credentials`.
- New backend auth policy blocked unauthenticated calls.

Effect:
- Frontend shell loaded, but no action data rendered.

Fix:
- Added:
  - `backend.auth.dangerouslyDisableDefaultAuthPolicy: true`
  for local/dev operation.

Validation:
- `/api/scaffolder/v2/actions` returned HTTP 200 with action list.

### 3) `/create/actions` blank page (phase 2)
Symptoms:
- Browser console error:
  - `Missing required config value at 'app.title' in 'app'`

Cause:
- Required Backstage config key `app.title` was absent.

Effect:
- React runtime crash in SignIn page path.

Fix:
- Added:
  - `app.title: NeuroScale Platform`

Validation:
- Runtime config includes `app.title`; page no longer crashes for this reason.

### 4) Backstage frontend/backend port mismatch
Symptoms:
- Accessed on `http://localhost:7010` but frontend still called backend configured as `http://localhost:7007`.

Cause:
- `app.baseUrl` and `backend.baseUrl` were set to 7007 while user session used 7010.

Effect:
- UI loaded but API calls failed or appeared blank.

Fix:
- Set both to `http://localhost:7010`.

Validation:
- Injected runtime config showed both base URLs on 7010.

### 5) Repeated port-forward failures
Symptoms:
- `unable to listen on any of the requested ports`
- `Only one usage of each socket address...`

Cause:
- Stale background `kubectl port-forward` processes occupying ports.

Effect:
- Intermittent local access failures and confusing diagnostics.

Fix:
- Killed stale forwarding terminals/processes and re-established clean forwards.

Validation:
- Stable port-forward sessions on selected ports.

### 6) GitHub token issues
Symptoms:
- PR creation failed or inconsistent behavior.

Cause:
- Placeholder/invalid token values and env propagation timing.

Effect:
- Backstage unable to open PRs reliably.

Fix:
- Updated Secret with real token.
- Restarted Backstage deployment to reload env vars.
- Verified token presence by length checks in Secret and running container.

Validation:
- Scaffolder `Open pull request` step completed successfully.

### 7) PR merged but child app stayed `OutOfSync`
Symptoms:
- `demo-iris-2` app existed in Argo but failed to apply resources.
- Error from webhook:
  - `no endpoints available for service kserve-webhook-server-service`

Cause:
- KServe controller deployment was unhealthy:
  - sidecar `kube-rbac-proxy` stuck in `ImagePullBackOff`
  - initial image `gcr.io/kubebuilder/kube-rbac-proxy:v0.13.1` unreachable
  - attempted `registry.k8s.io/kube-rbac-proxy:v0.13.1` not found

Effect:
- Admission webhooks unavailable.
- Argo sync of `InferenceService` failed.

Fix:
- Added serving-stack patch for `kserve-controller-manager`.
- Final working patch removed failing `kube-rbac-proxy` sidecar in this local lab context.
- Files:
  - `infrastructure/serving-stack/kustomization.yaml`
  - `infrastructure/serving-stack/patches/kserve-controller-kube-rbac-proxy-image.yaml`

Validation:
- `kserve-controller-manager` became `1/1 ready`.
- `kserve-webhook-server-service` gained endpoints.
- `demo-iris-2` synced and became healthy.

### 8) Git push rejected during fix rollout
Symptoms:
- `failed to push some refs... remote contains work that you do not have locally`

Cause:
- `main` moved ahead (parallel merges/commits).

Effect:
- Fix commit not initially visible to ArgoCD.

Fix:
- `git fetch origin`
- `git rebase origin/main`
- `git push`

Validation:
- Remote `main` moved to new fix commits and Argo consumed them.

### 9) Inference call failures after endpoint was ready
Symptoms:
- `Could not resolve host: YOUR_MODEL_URL_HERE`
- Requests landing on `example.com` public page (405)
- Timeout to `172.20.0.3:80`
- HTTP `307` redirect from ingress

Cause:
- Placeholder URL used initially.
- Ingress host routing and TLS redirect behavior not matched in command path.
- Windows host connectivity to k3d LB IP differed from expected path.

Effect:
- False-negative inference verification despite healthy service.

Fix:
- Verified with direct predictor pod port-forward path for deterministic local proof.

Validation:
- Prediction succeeded:
  - `{"predictions":[1,1]}`

## What Changed in Repo During Week 3
- `backstage/templates/model-endpoint/template.yaml`
- `backstage/templates/model-endpoint/skeleton/apps/${{ values.name }}/inference-service.yaml`
- ~~`backstage/templates/model-endpoint/skeleton/infrastructure/apps/${{ values.name }}-app.yaml`~~ _(this skeleton file was removed in Milestone F — the ApplicationSet auto-discovers `apps/*` directories; per-app Application files are no longer generated)_
- `infrastructure/backstage/values.yaml`
- `infrastructure/serving-stack/kustomization.yaml`
- `infrastructure/serving-stack/patches/kserve-controller-kube-rbac-proxy-image.yaml`
- `.gitignore` (temporary chart/extraction artifacts)

## Known Tradeoffs and Risk Notes
- ~~`dangerouslyDisableDefaultAuthPolicy: true` is acceptable for local learning but not for production.~~ **RESOLVED in Milestone F:** replaced with `auth.providers.guest.dangerouslyAllowOutsideDevelopment: true`, which keeps the auth subsystem active and provides a real `user:default/guest` identity. Production uses GitHub OAuth via `values-prod.yaml`.
- Removing `kube-rbac-proxy` sidecar restores functionality quickly in local lab but reduces metrics endpoint hardening.
- Branch protection currently allows bypass by admin identity; this weakens strict GitOps governance guarantees.

## Operational Runbook (Current Working Path)

### Daily Morning Routine (Fast Start)
Use this when the cluster already exists and you are just resuming work after laptop shutdown.

1. Start Docker Desktop and wait until it is fully running.
2. Start the existing k3d cluster:

```sh
k3d cluster start neuroscale
```

3. Run a quick health gate before opening UIs:

```sh
kubectl get nodes
kubectl -n argocd get applications
kubectl -n kserve get deploy,pods
```

4. Re-open required tunnels (port-forwards always die after terminal/cluster stop):

Terminal 1 (ArgoCD):
```sh
kubectl port-forward svc/argocd-server -n argocd 8081:443
```

Terminal 2 (AI gateway via Kourier):
```sh
kubectl -n kourier-system port-forward svc/kourier 8082:80
```

Terminal 3 (Backstage, when needed):
```sh
kubectl -n backstage port-forward svc/neuroscale-backstage 7010:7007
```

5. Verify access:
- ArgoCD: `https://localhost:8081`
- Backstage: `http://localhost:7010/create`
- Backstage actions: `http://localhost:7010/create/actions`

6. If Backstage PR creation fails due to token/auth, run recovery:

```sh
read -s GITHUB_TOKEN
kubectl -n backstage create secret generic neuroscale-backstage-secrets \
  --from-literal=GITHUB_TOKEN="$GITHUB_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n backstage rollout restart deploy/neuroscale-backstage
kubectl -n backstage rollout status deploy/neuroscale-backstage --timeout=300s
```

### End of Day (Battery Save)
Stop the cluster when done:

```sh
k3d cluster stop neuroscale
```

Notes:
- After `k3d cluster start`, always re-run port-forward commands.
- If a port is busy, use a different local port or terminate stale port-forward processes.

### Backstage token setup
```sh
kubectl create ns backstage >/dev/null 2>&1 || true

read -s GITHUB_TOKEN
kubectl -n backstage create secret generic neuroscale-backstage-secrets \
  --from-literal=GITHUB_TOKEN="$GITHUB_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n backstage rollout restart deploy/neuroscale-backstage
kubectl -n backstage rollout status deploy/neuroscale-backstage --timeout=300s
```

### Backstage access
```sh
kubectl -n backstage port-forward svc/neuroscale-backstage 7010:7007
```

Open:
- `http://localhost:7010/create`
- `http://localhost:7010/create/actions`

### Argo and KServe verification
```sh
kubectl -n argocd get applications.argoproj.io
kubectl -n kserve get deploy,pods,svc,endpoints
kubectl -n default get inferenceservices.serving.kserve.io
```

### Deterministic inference verification (local)
```sh
# Get current predictor pod name for demo-iris-2
kubectl -n default get pods -l serving.knative.dev/revision=demo-iris-2-predictor-00001

# Port-forward to predictor runtime port
kubectl -n default port-forward pod/<predictor-pod-name> 18080:8080

# Predict
curl -sS -H "Content-Type: application/json" \
  -d '{"instances":[[6.8,2.8,4.8,1.4],[6.0,3.4,4.5,1.6]]}' \
  http://127.0.0.1:18080/v1/models/demo-iris-2:predict
```

Expected:
```json
{"predictions":[1,1]}
```

## Definition of Done (Week 3)
1. Backstage template is visible and runnable.
2. Template run opens PR with expected app and Argo files.
3. PR merge creates Argo child app.
4. Child app syncs without webhook errors.
5. New `InferenceService` reaches `Ready=True`.
6. Inference request returns predictions.

## Hardening Backlog (Post-Week 3)
1. ✅ Replace dev auth bypass with proper Backstage auth provider and sign-in policy. _(DONE in Milestone F: `dangerouslyDisableDefaultAuthPolicy: true` replaced by guest provider `dangerouslyAllowOutsideDevelopment: true`; production path uses GitHub OAuth in `values-prod.yaml`.)_
2. ⏳ Restore secure metrics proxy approach for KServe controller (use verified reachable image mirror). _(Still pending — `kube-rbac-proxy` sidecar remains removed; no accessible image mirror confirmed yet. See `docs/PROJECT_MEMORY.md` section 7.)_
3. ✅ Enforce strict branch protection with no personal bypass on `main`. _(DONE in Milestone F.)_
4. ✅ Add CI checks for required Backstage config keys (`app.title`, base URLs). _(Addressed via `scripts/ci/render_backstage.sh` which renders the full Helm chart output and validates the resulting Deployment spec in CI.)_
5. ✅ Add synthetic smoke test that runs template and verifies `InferenceService` readiness automatically. _(DONE: `scripts/smoke-test.sh` validates all milestone contracts including InferenceService readiness, Backstage availability, and Golden Path evidence end-to-end.)_

## Defense Drill (Explain Clearly)
- Why app-of-apps + per-endpoint child app was chosen.
- Why template catalog rules are required for `Template` entities.
- Why `401` on scaffolder actions caused blank UI despite 200 route response.
- Why missing webhook endpoints block Argo sync at admission time.
- Why ingress URL checks can be misleading in local clusters and how to prove inference deterministically.
