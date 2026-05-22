# NeuroScale Operational Runbook

> Documented recovery procedures for every failure mode encountered during platform development.

---

## 1. ArgoCD repo-server CrashLoopBackOff / Unknown State

**Symptom:** All ArgoCD applications show `Unknown` sync and health status. The comparison engine cannot run.

**Root Cause:** repo-server pod crashed due to controller dependency ordering, resource pressure, or initialization race condition.

**Recovery:**

```bash
# Step 1: Confirm repo-server is the issue
kubectl -n argocd get pods | grep repo-server
# Look for: CrashLoopBackOff or 0/1 Ready

# Step 2: Restart repo-server
kubectl -n argocd rollout restart deploy/argocd-repo-server

# Step 3: Wait for stability
kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=120s

# Step 4: Force hard refresh on stuck applications
kubectl -n argocd patch application neuroscale-infrastructure \
  --type merge \
  -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'

# Step 5: Verify recovery
kubectl -n argocd get applications
# All should show Synced/Healthy within 3 minutes
```

**Prevention:** Include repo-server health in monitoring. The smoke test checks this automatically.

---

## 2. Kyverno Webhook Disrupts ArgoCD Sync Loop

**Symptom:** After Kyverno install/restart, other ArgoCD applications enter `Unknown` state. `kubectl apply` operations time out.

**Root Cause:** Kyverno registers webhook configurations before its pods are ready. During the 2-3 minute initialization window, all Kubernetes API mutations pass through a non-responsive webhook, causing timeouts.

**Recovery:**

```bash
# Step 1: Check Kyverno readiness
kubectl -n kyverno get pods
# Wait until all pods show Running/Ready

# Step 2: If Kyverno pods are healthy but webhooks are stale
kubectl delete validatingwebhookconfiguration kyverno-resource-validating-webhook-cfg 2>/dev/null
kubectl delete mutatingwebhookconfiguration kyverno-resource-mutating-webhook-cfg 2>/dev/null
# Kyverno will recreate them once healthy

# Step 3: Restart ArgoCD repo-server if applications are stuck
kubectl -n argocd rollout restart deploy/argocd-repo-server
```

**Prevention:** Use `webhookAnnotations` ConfigMap patch to suppress automatic webhook registration during install. Deploy Kyverno before other platform components during initial bootstrap.

---

## 3. KServe InferenceService Stuck Not Ready

**Symptom:** InferenceService shows `READY=False` with no URL populated.

**Possible Causes:**

### A) Ingress Mismatch (Istio vs Kourier)
```bash
# Check KServe controller logs
kubectl -n kserve logs deploy/kserve-controller-manager --tail=30

# If you see: "virtual service not found"
# → The inferenceservice-config ConfigMap still has disableIstioVirtualHost: false
# Fix: Verify the Kustomize patch is applied
kubectl -n kserve get configmap inferenceservice-config -o yaml | grep disableIstioVirtualHost
# Should show: true
```

### B) Predictor Pod Not Starting
```bash
# Check predictor pod status
kubectl -n default get pods -l serving.kserve.io/inferenceservice=<name>

# If ImagePullBackOff: check storageUri and container image
# If CrashLoopBackOff: check model format compatibility
kubectl -n default logs <predictor-pod> --tail=50
```

### C) Knative/Kourier Not Routing
```bash
# Check Kourier health
kubectl -n kourier-system get pods
kubectl -n knative-serving get pods

# Check Knative services
kubectl -n default get ksvc
```

---

## 4. Backstage CrashLoopBackOff

**Symptom:** Backstage pod restarts repeatedly with startup probe failures.

**Root Cause:** Helm values hierarchy mis-nesting. Backstage dependency chart requires values under `backstage.backstage.*` (double-nested), not `backstage.*`.

**Recovery:**

```bash
# Step 1: Check current probe configuration
kubectl -n backstage get deploy neuroscale-backstage -o yaml | grep -A 5 startupProbe

# Step 2: If probes show default values (not custom), values nesting is wrong
# Verify values.yaml has correct nesting:
# backstage:
#   backstage:
#     startupProbe:
#       initialDelaySeconds: 120
#       failureThreshold: 30

# Step 3: After fixing values, restart
kubectl -n backstage rollout restart deploy/neuroscale-backstage
```

**Prevention:** CI runs `helm template` and validates rendered probe values via `scripts/ci/render_backstage.sh`.

---

## 5. Backstage GitHub Token Expired / Missing

**Symptom:** Backstage scaffolder returns 401 errors. `/create/actions` page is blank.

**Recovery:**

```bash
# Step 1: Generate new GitHub Personal Access Token
# Scopes needed: repo, workflow

# Step 2: Update Kubernetes secret
read -s GITHUB_TOKEN
kubectl -n backstage create secret generic neuroscale-backstage-secrets \
  --from-literal=GITHUB_TOKEN="$GITHUB_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -

# Step 3: Restart Backstage to pick up new secret
kubectl -n backstage rollout restart deploy/neuroscale-backstage

# Step 4: Verify
kubectl -n backstage rollout status deploy/neuroscale-backstage --timeout=180s
```

---

## 6. CI False-Green on Policy Checks

**Symptom:** CI pipeline passes but Kyverno should have caught violations.

**Root Cause:** `kyverno-cli apply` may exit 0 even when violations exist. Single `--resource` flag silently ignores paths after the first.

**Fix (already implemented):**

The CI workflow uses:
1. Separate `--resource` flag per file
2. Dual-check: exit code AND stdout parsing for `FAIL` markers
3. Grep for `fail: [1-9]` pattern in output

**Verification:**

```bash
# Manually test policy simulation locally
docker run --rm -v "$PWD:/work" -w /work ghcr.io/kyverno/kyverno-cli:v1.12.5 \
  apply infrastructure/kyverno/policies/*.yaml \
  --resource apps/test-app/deployment.yaml
```

---

## 7. Quick Health Check

```bash
# Full health assessment (30 seconds)
echo "=== Nodes ===" && kubectl get nodes
echo "=== ArgoCD ===" && kubectl -n argocd get applications
echo "=== KServe ===" && kubectl -n kserve get deploy
echo "=== Inference ===" && kubectl -n default get inferenceservices
echo "=== Policies ===" && kubectl get clusterpolicies
echo "=== Backstage ===" && kubectl -n backstage get pods
echo "=== Quotas ===" && kubectl -n default get resourcequota,limitrange
```

Or run the automated smoke test:

```bash
bash scripts/smoke-test.sh
```
