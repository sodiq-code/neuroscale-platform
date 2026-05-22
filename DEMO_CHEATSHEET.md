# NeuroScale — Demo Cheat Sheet

> Deterministic demo sequence. Under 3 minutes. Cannot fail.

---

## Pre-Demo Setup (run once)

```bash
# 1. Bootstrap the cluster (5 min first time)
bash scripts/bootstrap.sh

# 2. Wait for convergence (2-5 min)
watch kubectl -n argocd get applications

# 3. Open all UIs
bash scripts/port-forward-all.sh

# 4. Verify everything works
bash scripts/smoke-test.sh
```

---

## Demo Sequence

### Scene 1: The Broken State (0:00–0:20)

**Show what used to happen.**

```bash
# Show a non-compliant manifest that would have deployed before
cat <<'EOF'
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: bad-model
  namespace: default
  # NO owner label
  # NO cost-center label
spec:
  predictor:
    model:
      modelFormat:
        name: sklearn
      storageUri: "gs://kfserving-examples/models/sklearn/1.0/model"
      # NO resource limits
EOF
echo ""
echo "Before NeuroScale: this would deploy. No warning. No block."
```

### Scene 2: Self-Service Golden Path (0:20–0:50)

**Show the Backstage form creating a change.**

```bash
# Open Backstage
# Navigate: http://localhost:7010/create
# Select: "KServe model endpoint"
# Fill form:
#   - Endpoint name: my-new-model
#   - Model format: sklearn
#   - Owner: ml-platform
#   - Cost center: cc-ml
# Click "Create"
# Show: PR created automatically on GitHub
```

### Scene 3: CI Refusing a Bad Change (0:50–1:20)

**Show policy enforcement at PR time.**

```bash
# Try to apply a non-compliant InferenceService directly
kubectl apply -f - <<EOF
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: bad-model
  namespace: default
spec:
  predictor:
    model:
      modelFormat:
        name: sklearn
      storageUri: "gs://kfserving-examples/models/sklearn/1.0/model"
EOF
# Expected: Kyverno denies it
# "admission webhook denied the request: must set metadata.labels.owner and metadata.labels.cost-center"
```

### Scene 4: GitOps Sync (1:20–1:50)

**Show ArgoCD managing everything.**

```bash
# Show ArgoCD dashboard - all apps healthy
# https://localhost:8081
# Username: admin
# Password: (from bootstrap output)

# Show the ApplicationSet auto-discovery
kubectl -n argocd get applications | grep -E "NAME|neuroscale"

# Show self-healing
kubectl delete deploy nginx-test -n default
echo "Waiting for ArgoCD to self-heal..."
sleep 20
kubectl get deploy nginx-test -n default
# Result: recreated automatically
```

### Scene 5: Working Prediction (1:50–2:10)

**Show the endpoint works.**

```bash
# Get predictor pod
POD=$(kubectl -n default get pods -l serving.kserve.io/inferenceservice=demo-iris-2 \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

# Port-forward to predictor
kubectl -n default port-forward pod/$POD 18080:8080 &
sleep 2

# Send prediction
curl -sS -H "Content-Type: application/json" \
  -d '{"instances":[[6.8,2.8,4.8,1.4],[6.0,3.4,4.5,1.6]]}' \
  http://127.0.0.1:18080/v1/models/demo-iris-2:predict

# Expected: {"predictions":[1,1]}

# Kill port-forward
kill %1 2>/dev/null
```

### Scene 6: Failure Recovery (2:10–2:40)

**Show operational maturity.**

```bash
# Simulate ArgoCD repo-server failure
kubectl -n argocd delete pod -l app.kubernetes.io/name=argocd-repo-server

# Show recovery
echo "ArgoCD repo-server deleted. Watching recovery..."
kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=120s

# Verify all apps recovered
kubectl -n argocd get applications
# All should show Synced/Healthy
```

### Scene 7: Final Architecture Shot (2:40–3:00)

```bash
# Run the full smoke test as the finale
bash scripts/smoke-test.sh --skip-drift
# Shows: PASS 21 / FAIL 0
```

---

## Emergency Aliases (paste before demo)

```bash
alias k='kubectl'
alias kga='kubectl -n argocd get applications'
alias kgp='kubectl get pods -A'
alias smoke='bash scripts/smoke-test.sh --skip-drift'
alias pf='bash scripts/port-forward-all.sh'
```

---

## If Something Goes Wrong

| Symptom | Fix |
|---------|-----|
| ArgoCD shows Unknown | `kubectl -n argocd rollout restart deploy/argocd-repo-server` |
| InferenceService not Ready | Check KServe controller: `kubectl -n kserve logs deploy/kserve-controller-manager --tail=20` |
| Backstage CrashLoopBackOff | Check probe values: `kubectl -n backstage describe deploy neuroscale-backstage` |
| Kyverno not blocking | Check policies: `kubectl get clusterpolicies` |
