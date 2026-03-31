# Reality Check: Milestone 3 — Backstage Golden Path

> **This is not a tutorial where everything works.** This document records every failure encountered while implementing the Backstage Golden Path: from the portal showing a blank page to a PR-merged model endpoint that refused to deploy. Nine distinct failures. Each one taught something a happy-path tutorial cannot.

---

## What We Were Trying to Prove

Milestone C goal: a developer fills in a Backstage form, the platform opens a GitHub PR with two files, the PR is merged, ArgoCD deploys a new `InferenceService`, and the endpoint responds to a prediction request.

> **Milestone F update:** In the original Milestone C design the PR contained two files: `apps/<name>/inference-service.yaml` and `infrastructure/apps/<name>-app.yaml`. The second file was eliminated in Milestone F when the `neuroscale-model-endpoints` ApplicationSet was introduced. The ApplicationSet auto-discovers every directory under `apps/` and creates the ArgoCD Application automatically, so no per-app registration file is needed. The overall flow (form → PR → merge → deploy → Ready) is unchanged; only the number of files in the PR changed from two to one.

The demo contract end-to-end:

```
Backstage form -> PR opened -> merge -> ArgoCD sync -> InferenceService Ready -> curl returns {"predictions":[1,1]}
```

---

## Failure 1: Backstage Template Not Visible in Catalog — Catalog Ingestion Silently Rejects Template Kind Without Explicit allow Rule

### Symptom

After adding the template file at `backstage/templates/model-endpoint/template.yaml` and registering it in `infrastructure/backstage/values.yaml`, the template did not appear in Backstage's `/create` page. No error was visible in the UI.

Checking the Backstage backend logs:

```
$ kubectl -n backstage logs deploy/neuroscale-backstage --tail=50
...
[backstage] warn  Failed to process location {"location":{"type":"url","target":"https://github.com/sodiq-code/neuroscale-platform/blob/main/backstage/templates/model-endpoint/template.yaml"},"error":"NotAllowedError: Forbidden: entity of kind Template is not allowed from that location"}
```

### Root Cause

The Backstage catalog configuration allows only specific entity kinds from each registered location. The default allow list for repository-based locations does not include `Template`. Without an explicit `allow: [Template]` rule for that URL, entities of kind `Template` are silently rejected.

This is a security-by-default behavior in Backstage's catalog ingestion. The error message only appears in server logs, not in the UI, so from the developer's perspective the template simply doesn't exist.

### Fix

In `infrastructure/backstage/values.yaml`, added an explicit allow rule for the template location:

```yaml
backstage:
  backstage:
    appConfig:
      catalog:
        locations:
          - type: url
            target: https://github.com/sodiq-code/neuroscale-platform/blob/main/backstage/templates/model-endpoint/template.yaml
            rules:
              - allow: [Template]
```

After rolling out the updated Backstage deployment:

```
$ kubectl -n backstage rollout restart deploy/neuroscale-backstage
$ kubectl -n backstage rollout status deploy/neuroscale-backstage --timeout=300s
deployment "neuroscale-backstage" successfully rolled out
```

The template appeared in `/create` within 60 seconds.

### Business Impact

30 minutes debugging a problem that generates no visible error in the UI. For a platform team deploying Backstage for internal users, this silent failure means developers see an empty template catalog and assume the platform doesn't work — not that a config rule is missing.

---

## Failure 2: Backstage /create/actions Blank Page — Scaffolder Actions API Returns 401 Due to Missing Internal Auth Policy

### Symptom

Even after the template was visible, clicking into the template form showed a blank page. The browser developer console revealed:

```
GET /api/scaffolder/v2/actions HTTP/1.1 401 Unauthorized
{"error":{"name":"AuthenticationError","message":"Missing credentials"}}
```

The page route returned HTTP 200 (the React app loaded), but the actions API returned 401, so the form had no data to render.

### Root Cause

Backstage's new backend architecture (introduced in 1.x) adds an internal authentication policy that requires all service-to-service calls to include a valid Backstage token. The scaffolder frontend makes an internal API call to list available actions. Because no auth provider was configured for local development, this internal call was rejected.

This is a breaking change from older Backstage versions where the actions endpoint was unauthenticated. The migration guide mentions this but does not surface it during initial deployment.

### Fix

Added to `infrastructure/backstage/values.yaml`:

```yaml
backstage:
  backstage:
    appConfig:
      backend:
        auth:
          dangerouslyDisableDefaultAuthPolicy: true
```

After this change, the actions API returned HTTP 200 with the full list of available actions.

**Production note:** `dangerouslyDisableDefaultAuthPolicy: true` is acceptable for local development but must not be used in any shared or production environment. The correct fix is to configure an identity provider (GitHub OAuth, Google, etc.) with a proper sign-in policy.

### Business Impact

An empty scaffolder form is indistinguishable from a misconfigured form to an end user. The 401 error is only visible in browser developer tools — not in the UI. This is the third failure in this milestone that generated no visible error message for the person experiencing it.

---

## Failure 3: Backstage React Frontend Crashes on Load — Missing Required app.title Config Key Causes Blank White Screen

### Symptom

After the auth policy fix, reloading the Backstage page showed a blank white screen. The browser console showed:

```
Uncaught Error: Missing required config value at 'app.title' in 'app'
    at validateConfigSchema (config.esm.js:234)
    at BackstageApp.render (app.esm.js:891)
```

### Root Cause

The Backstage frontend requires `app.title` to be present in the runtime configuration. This key was absent from the `appConfig` section of `values.yaml`. The React application crashed on initialization before any content could render.

This is a required configuration key that is not documented prominently as "required on first boot." It is listed in the default `app-config.yaml` template that ships with a `backstage new app` scaffold — but since this deployment was adapted from Helm chart examples that omit the key, it was missing.

### Fix

Added to `infrastructure/backstage/values.yaml`:

```yaml
backstage:
  backstage:
    appConfig:
      app:
        title: NeuroScale Platform
        baseUrl: http://localhost:7010
      backend:
        baseUrl: http://localhost:7010
        cors:
          origin: http://localhost:7010
```

Note: `app.baseUrl` and `backend.baseUrl` were also absent and needed to match the port we use for port-forwarding (7010).

---

## Failure 4: Backstage CrashLoopBackOff — Helm Dependency Values Mis-Nesting Causes Startup Probe to Use Default 2s Delay

### Symptom

This failure occurred before the above issues, during initial Backstage deployment setup. The Backstage pod entered `CrashLoopBackOff` with rapid restarts:

```
$ kubectl get pods -n backstage -w
NAME                                    READY   STATUS             RESTARTS   AGE
neuroscale-backstage-7d9f5b8c4-xqr2m   0/1     CrashLoopBackOff   8          12m

$ kubectl describe pod neuroscale-backstage-7d9f5b8c4-xqr2m -n backstage
...
Events:
  Warning  Unhealthy  30s  kubelet  
    Startup probe failed: connect: connection refused
```

### Root Cause

See `infrastructure/INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md` for full details. Summary:

The Backstage Helm chart is a wrapper chart with `backstage` as a dependency. Configuration for the Backstage container itself must be nested under `backstage.backstage.*`, not `backstage.*`. The misconfiguration meant that probe settings and resource requests were silently ignored, so Kubernetes used default probe timings (2-second initial delay) that were far too aggressive for Backstage's ~90-second startup time.

The deployment used chart-default probes. Backstage needs:

```yaml
startupProbe:
  initialDelaySeconds: 120
  failureThreshold: 30
```

With default settings, the pod was killed before it could become healthy, triggering CrashLoopBackOff.

### Business Impact

Developer portal unavailable for the duration of the incident. Every rolling update that doesn't correct probe values will cause the same failure. This was the incident that directly motivated adding CI validation for rendered Helm manifests — if we had validated the final Deployment spec in CI before applying it, the wrong probe values would have been caught before deployment.

---

## Failure 5: Backstage Scaffolder PR Creation Fails — GitHub Token Secret Contains Placeholder Value Not Replaced After Setup

### Symptom

After the Backstage portal was stable and the template was running, the scaffolder's "Open pull request" step showed a progress spinner for 30 seconds and then failed with:

```
Error: Request failed with status 401: Bad credentials
```

No PR was created in GitHub.

### Root Cause

The Kubernetes Secret `neuroscale-backstage-secrets` contained a placeholder `GITHUB_TOKEN` value from an earlier setup step. When the secret was created, the token was set to `<YOUR_TOKEN_HERE>` literally. The environment variable was present (satisfying `kubectl describe secret` output), but the value was not a valid token.

A secondary issue: after updating the secret with the correct token, the running Backstage pod did not pick up the change because environment variables from Secrets are injected at pod start time, not dynamically. The pod needed to be restarted.

### Fix

```bash
# Update the secret with a valid token
read -s GITHUB_TOKEN
kubectl -n backstage create secret generic neuroscale-backstage-secrets \
  --from-literal=GITHUB_TOKEN="$GITHUB_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart the deployment to reload env vars from the new secret
kubectl -n backstage rollout restart deploy/neuroscale-backstage
kubectl -n backstage rollout status deploy/neuroscale-backstage --timeout=300s

# Verify the token is present (check length, not value)
kubectl -n backstage exec deploy/neuroscale-backstage -- sh -c 'echo ${#GITHUB_TOKEN} chars'
```

After restart, PR creation succeeded.

### Business Impact

This failure is subtle because `kubectl describe secret` shows the key exists and the value has bytes — it does not show whether the value is a valid token or a placeholder string. Developers who copied a template and forgot to replace a placeholder value will see the secret "working" from the Kubernetes perspective while the application fails to authenticate.

---

## Failure 6: PR Merged but ArgoCD demo-iris-2 Stays OutOfSync — kube-rbac-proxy Fix Applied via kubectl Not Committed to Git, Reverted by selfHeal

### Symptom

The Backstage scaffolder created a PR with the correct two files (as designed at the time):

- `apps/demo-iris-2/inference-service.yaml`
- `infrastructure/apps/demo-iris-2-app.yaml` _(removed in Milestone F — the `neuroscale-model-endpoints` ApplicationSet now auto-discovers `apps/*` directories; per-app Application files are no longer generated or required)_

The PR passed CI checks and was merged. ArgoCD detected the new `demo-iris-2-app.yaml` and created the child Application. But the child app immediately showed `OutOfSync/Degraded`:

```
$ kubectl -n argocd get application demo-iris-2
NAME          SYNC STATUS   HEALTH STATUS
demo-iris-2   OutOfSync      Degraded

$ kubectl -n argocd describe application demo-iris-2
...
Message: one or more objects failed to apply, reason: 
  Internal error occurred: failed calling webhook 
  "inferenceservice.kserve-webhook-server.validator.webhook": 
  failed to call webhook: Post 
  "https://kserve-webhook-server-service.kserve.svc:443/validate-serving-kserve-io-v1beta1-inferenceservice?timeout=10s": 
  no endpoints available for service "kserve-webhook-server-service"
```

### Root Cause

This was the `kube-rbac-proxy` ImagePullBackOff failure from Milestone 2 (see `REALITY_CHECK_MILESTONE_2_KSERVE_SERVING.md`) reappearing after a cluster restart. When the cluster was stopped and restarted for the Milestone C work session, the `kube-rbac-proxy` sidecar patch had not been persisted to the repo yet — only applied manually. On cluster restart, the original (unpatched) Deployment was reconciled, the sidecar failed to pull, and the webhook lost its endpoint.

The root cause of *this specific recurrence* was that the fix was not committed to Git. It was applied with `kubectl patch` directly. ArgoCD's `selfHeal: true` reverted it on the next sync cycle.

### Fix

Committed the `kube-rbac-proxy` removal patch to the serving-stack kustomization (it was already added in Milestone 2 but had not been pushed before the cluster restart):

```bash
# Verify patch is in kustomization.yaml
cat infrastructure/serving-stack/kustomization.yaml | grep -A2 patches

# Commit and push
git add infrastructure/serving-stack/
git commit -m "serving-stack: persist kube-rbac-proxy removal patch"
git push origin main
```

ArgoCD picked up the change within 3 minutes and the controller restarted in the correct configuration.

**Key lesson:** Any fix applied with `kubectl` directly in a GitOps-managed cluster is temporary. The next sync cycle will revert it. Every fix must be committed to Git to survive.

### Business Impact

The PR-merged-but-nothing-deployed experience is the worst possible failure for a Golden Path demo. The developer did everything correctly. The PR was created correctly. The CI passed. The merge happened. And then nothing worked. The failure was invisible to the developer and required cluster-operator-level debugging to diagnose.

---

## Failure 7: Inference Endpoint Returns HTTP 307 Redirect — k3d Traefik Intercepts Request Before Reaching Kourier

### Symptom

After `demo-iris-2` became `Ready=True`, the initial inference test returned an unexpected redirect:

```
$ curl -v \
  -H 'Content-Type: application/json' \
  -d '{"instances":[[6.8,2.8,4.8,1.4]]}' \
  http://172.20.0.3/v1/models/demo-iris-2:predict

< HTTP/1.1 307 Temporary Redirect
< Location: https://172.20.0.3/v1/models/demo-iris-2:predict
```

The cluster's load balancer IP (172.20.0.3, the k3d node) was responding with a TLS redirect — redirecting HTTP to HTTPS on a cluster with no TLS configured for inference endpoints.

### Root Cause

k3d's built-in traefik ingress was intercepting the request and applying an HTTP-to-HTTPS redirect rule before it reached Kourier. The k3d cluster's traefik `IngressRoute` was configured with HTTPS enforcement by default.

The request never reached Kourier or the Knative routing layer at all.

### Fix

Used direct pod port-forward as the canonical local verification method:

```bash
# Find predictor pod
kubectl -n default get pods -l serving.knative.dev/revision=demo-iris-2-predictor-00001 \
  -o jsonpath='{.items[0].metadata.name}'

# Port-forward directly to the pod
kubectl -n default port-forward \
  pod/demo-iris-2-predictor-00001-deployment-<hash> 18080:8080

# Predict (no Host header, no traefik, no Kourier)
curl -sS \
  -H "Content-Type: application/json" \
  -d '{"instances":[[6.8,2.8,4.8,1.4],[6.0,3.4,4.5,1.6]]}' \
  http://127.0.0.1:18080/v1/models/demo-iris-2:predict
```

Output:

```json
{"predictions":[1,1]}
```

Milestone C was complete.

### Business Impact

False-negative verification. A healthy inference endpoint looked broken because the test path hit an intermediary (traefik) that was not in scope for inference routing. For a demo or interview, spending time on this without understanding the network topology looks like a fundamental misunderstanding of the system.

---

## What Milestone 3 Actually Proves (After the Failures)

Final state after all nine failures were resolved:

```
$ kubectl -n default get inferenceservice demo-iris-2
NAME          URL                                        READY   AGE
demo-iris-2   http://demo-iris-2.default.example.com    True    25m

$ curl -sS \
  -H "Content-Type: application/json" \
  -d '{"instances":[[6.8,2.8,4.8,1.4],[6.0,3.4,4.5,1.6]]}' \
  http://127.0.0.1:18080/v1/models/demo-iris-2:predict
{"predictions":[1,1]}
```

**Interview-ready framing:** "The Golden Path demo is a chain of seven moving parts: Backstage config, GitHub auth, ArgoCD app-of-apps, KServe controller, Knative routing, Kourier gateway, and the predictor pod. In production, any link in that chain can fail independently. The debugging process for Milestone 3 is a direct map to what a platform SRE does on an on-call shift."

---

## Debugging Commands Reference: Backstage Catalog Ingestion, Scaffolder Auth, ArgoCD Sync, and Inference Verification

```bash
# Check Backstage catalog ingestion errors
kubectl -n backstage logs deploy/neuroscale-backstage | grep -i "warn\|error\|fail"

# Check Backstage runtime config (injected via ConfigMap)
kubectl -n backstage describe configmap neuroscale-backstage-app-config

# Check scaffolder task logs (in Backstage UI at /create/tasks/<task-id>)
# Or via API:
# GET http://localhost:7010/api/scaffolder/v2/tasks/<task-id>/eventstream

# Check ArgoCD child app sync status
kubectl -n argocd get applications
kubectl -n argocd describe application demo-iris-2

# Check InferenceService conditions
kubectl -n default describe inferenceservice demo-iris-2

# Check admission webhook endpoints
kubectl -n kserve get endpoints kserve-webhook-server-service

# Verify GitHub token in running container (check length only)
kubectl -n backstage exec deploy/neuroscale-backstage -- sh -c 'echo ${#GITHUB_TOKEN}'
```

---

## See Also

- `docs/archive/MILESTONE_C_POSTMORTEM.md` — full implementation contract and runbook
- `infrastructure/INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md` — detailed RCA for the CrashLoopBackOff
- `backstage/templates/model-endpoint/template.yaml` — the Golden Path template
- `infrastructure/backstage/values.yaml` — Backstage Helm configuration
