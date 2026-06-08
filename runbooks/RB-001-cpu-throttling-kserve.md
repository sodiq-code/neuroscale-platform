# CPU Throttling on KServe InferenceService — Runbook #1

**Tags:** cpu, throttling, kserve, latency, memory
**Severity:** P1 — causes P99 latency breach and elevated error rates
**Date documented:** 2024-11-03 (Hermes Agent GEPA loop — Skill Document)
**Cluster:** neuroscale-k3d / production-analog

## Problem Description

When a KServe InferenceService (sklearn predictor) experiences sudden load spikes
combined with under-provisioned CPU limits, the predictor pod enters CPU throttling.
This manifests as:
- P99 latency spikes from ~150ms to 800ms–1200ms
- Error rate increases from <1% to 8–15%
- Arize Phoenix traces show long `predict` spans with `CPU_THROTTLE` status

## Root Cause

The ClusterServingRuntime (kserve-sklearn-server) has conservative CPU requests (100m)
that do not scale with load. Under concurrent inference requests, the Linux CFS scheduler
throttles the container, causing queue buildup.

## Recovery Steps

1. Identify the affected InferenceService: `kubectl get isvc -n default`
2. Check predictor pod CPU throttle rate: `kubectl top pod -n default | grep demo-iris`
3. Edit the InferenceService manifest: increase `resources.requests.cpu` to `250m` and `limits.cpu` to `1000m`
4. Also increase `resources.requests.memory` from `256Mi` to `512Mi` to prevent OOM during recovery
5. Commit the updated manifest to the GitOps repo via a Merge Request
6. Wait for ArgoCD to detect the commit and reconcile (~30s with selfHeal: true)
7. Verify predictor pod restarts and becomes Ready: `kubectl get pods -n default -w`
8. Validate P99 latency returns to <300ms via Arize Phoenix dashboard
9. Close the incident in the runbook log

## Kyverno Guardrail Notes

Ensure the new resource values comply with the `require-resource-requests-limits` policy.
The default namespace ResourceQuota caps total CPU requests at 4 cores — validate before committing.
The `disallow-latest-image-tag` policy will reject any attempted image change to `:latest`.

## HITL Checkpoint

The autonomous agent MUST pause for human approval before pushing the MR to production.
Reason: resource limit changes affect cluster-wide quota and require cost-center sign-off.

## Verification

```bash
# After ArgoCD sync:
kubectl top pod -n default | grep demo-iris
# Expected: CPU < 200m, no throttle signal

# Send test inference:
curl -sS -H "Content-Type: application/json" \
  -d '{"instances":[[6.8,2.8,4.8,1.4]]}' \
  http://localhost:8082/v1/models/demo-iris-2:predict
# Expected: {"predictions":[1]} within 200ms

# Check Arize Phoenix:
# P99 latency should return to <300ms within 5 minutes of pod restart
```

## Related Runbooks

- RB-002: KServe Pod OOM Kill
- RB-007: ArgoCD Sync Recovery
- RB-009: Kyverno Policy Denial Debugging
