# NeuroScale — Before: The Broken State

> What existed before this transformation.

---

## The Platform Was Abandoned

NeuroScale started as a promising MLOps platform concept — a self-service system for deploying AI inference endpoints on Kubernetes. But the initial implementation was broken, manual, and operationally dangerous.

**There was no working platform. There was a collection of broken parts.**

---

## What Was Broken

### 1. CrashLoopBackOff Everywhere

```
$ kubectl get pods -n backstage
NAME                                    READY   STATUS             RESTARTS
neuroscale-backstage-6b8f4c9d7-x2k9p   0/1     CrashLoopBackOff   14

$ kubectl get pods -n argocd
argocd-repo-server-7d9f5b8c4-xqr2m     0/1     CrashLoopBackOff   7
```

The developer portal (Backstage) was in a crash loop due to incorrect Helm values nesting — probe timings were silently ignored, causing Kubernetes to kill the pod before it could start. The ArgoCD repo-server was failing due to controller dependency ordering, leaving all applications in `Unknown` state.

### 2. Manual kubectl apply Workflow

```bash
# This was the "deployment process"
vim inference-service.yaml      # Edit YAML by hand
kubectl apply -f inference-service.yaml  # Hope it works
kubectl get inferenceservice    # Check if it stuck
# If it fails: Google the error, try again, repeat
```

There was no self-service path. Every model deployment required hand-editing YAML and running `kubectl apply` directly against the cluster. One typo = broken deployment. No review process. No guardrails.

### 3. No Policy Enforcement

```bash
# This was possible — and nobody would know until it broke something
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dangerous-workload
spec:
  template:
    spec:
      containers:
      - name: app
        image: random:latest      # Floating tag — non-reproducible
        securityContext:
          runAsUser: 0            # Running as root
        # No resource limits      # Unbounded resource consumption
EOF
# Result: deployed successfully. No warning. No block. Nothing.
```

Anyone could deploy root containers with no resource limits and floating image tags. No admission control. No CI validation. No cost attribution.

### 4. Broken KServe Ingress

```
$ kubectl get inferenceservice sklearn-iris
NAME           URL   READY   PREV   LATEST   AGE
sklearn-iris         False                    8m

$ kubectl -n kserve logs deploy/kserve-controller-manager --tail=10
ERROR  Failed to reconcile ingress
  {"error": "virtual service not found: sklearn-iris.default.svc.cluster.local"}
```

KServe's default configuration assumed Istio as the ingress provider, but the cluster ran Kourier. The controller entered an infinite error loop trying to create Istio VirtualService objects that would never exist. No inference endpoint was reachable.

### 5. Configuration Drift

```bash
# Someone fixes something manually in the cluster
kubectl edit deployment nginx-test -n default
# Git and cluster are now out of sync
# Nobody knows. Nothing alerts. Drift accumulates silently.
```

No GitOps self-healing. No drift detection. Manual cluster changes went unnoticed and accumulated until the next deployment broke in unpredictable ways.

### 6. No CI Validation

Pull requests merged without any validation:
- No schema checking (malformed YAML reached the cluster)
- No policy simulation (non-compliant manifests were never caught before merge)
- No resource delta awareness (nobody knew the cost impact of a change)

### 7. OOMKilled Risk

```
# Istio control plane alone: ~1 GB memory overhead
# On a k3d cluster with 8 GB shared with Docker Desktop:
# Backstage + KServe + ArgoCD + Istio = memory exhaustion
$ kubectl top nodes
NAME                      CPU(cores)   MEMORY(bytes)
k3d-neuroscale-server-0   890m         7124Mi/8192Mi  # 87% memory used
```

The architecture choice of Istio over Kourier was consuming resources that the platform couldn't afford, making the demo non-functional on any standard development machine.

---

## The Human Cost

- **Developers feared deploying models.** The process was manual, error-prone, and had no safety net.
- **Operators couldn't trust the cluster.** Manual changes created invisible drift.
- **Nobody could reproduce the environment.** No bootstrap script. No smoke tests. Setup required tribal knowledge.
- **Cost was invisible.** No labels, no attribution, no way to know which team consumed what.

---

## Summary: The Before State

| Aspect | Status |
|--------|--------|
| Developer self-service | None — manual kubectl only |
| Deployment safety | None — no policy enforcement |
| Configuration drift | Undetected — no GitOps self-heal |
| CI/CD validation | None — no schema or policy checks |
| Inference endpoints | Broken — Istio/Kourier mismatch |
| Cost visibility | None — no labels or attribution |
| Operational runbooks | None — tribal knowledge only |
| Environment reproducibility | None — no bootstrap automation |
| Platform health monitoring | None — no smoke tests |

**This was not a platform. It was a collection of broken infrastructure that required expert knowledge to operate and had no safety guarantees.**
