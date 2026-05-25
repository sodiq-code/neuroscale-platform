# KServe InferenceService Not Ready — Runbook #5

**Tags:** kserve, notready, ingress, kourier, istio, storageuri
**Severity:** P1 — inference endpoint unavailable
**Date documented:** 2024-10-22 (Hermes Agent GEPA loop — Skill Document)

## Problem Description

InferenceService shows READY=False with no URL populated after 5+ minutes.

## Diagnosis Tree

### Case A: Ingress Mismatch (Istio vs Kourier)
- Signal: `kubectl -n kserve logs deploy/kserve-controller-manager` shows "virtual service not found"
- Fix: Verify `disableIstioVirtualHost: true` in inferenceservice-config ConfigMap
  - `kubectl -n kserve get configmap inferenceservice-config -o yaml | grep disableIstio`
  - If false: apply the Kustomize patch at `infrastructure/serving-stack/patches/inferenceservice-config-ingress.yaml`

### Case B: storageUri Unreachable
- Signal: Predictor pod shows ImagePullBackOff or CrashLoopBackOff  
- Fix: Verify the GCS bucket URI is correct and publicly accessible
  - `kubectl -n default get pod -l serving.kserve.io/inferenceservice=demo-iris-2`
  - `kubectl -n default logs <pod-name> -c kserve-container`

### Case C: Resource Quota Exceeded
- Signal: Pod in Pending state with `Insufficient cpu` or `Insufficient memory`
- Fix: Check namespace quota: `kubectl get resourcequota -n default`
  - Either reduce other workloads or update the InferenceService resource requests downward

### Case D: Kyverno Webhook Blocking
- Signal: `kubectl get events -n default | grep kyverno`
- Fix: See RB-009 for policy compliance steps

## Recovery Steps

1. Run diagnosis tree above to identify case
2. Apply the appropriate fix
3. For Cases A/B/C: the fix does NOT require GitOps — these are platform-level configuration
4. For Case D: requires a compliant manifest MR (see RB-009)
5. After fix: `kubectl get isvc -n default -w` — wait for READY=True

## Verification

```bash
kubectl get isvc demo-iris-2 -n default
# Expected: READY=True, URL=http://demo-iris-2.default.example.com

# Test inference:
kubectl -n default port-forward pod/$(kubectl -n default get pod -l serving.kserve.io/inferenceservice=demo-iris-2 -o name | head -1) 18080:8080
curl -s -H "Content-Type: application/json" \
  -d '{"instances":[[6.8,2.8,4.8,1.4]]}' \
  http://127.0.0.1:18080/v1/models/demo-iris-2:predict
```
