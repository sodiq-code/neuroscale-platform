# Model Drift Detected — Rollback to Stable Version — Runbook #2

**Tags:** drift, rollback, kserve, sklearn, model-version, latency
**Severity:** P1 — prediction quality degradation impacts downstream services
**Date documented:** 2024-12-17 (Hermes Agent GEPA loop — Skill Document)

## Problem Description

Model drift occurs when the live inference model's prediction distribution diverges from
its training baseline. Detected via Arize Phoenix span attributes showing:
- Elevated classification error counts
- Distribution shift in input feature embeddings
- P99 latency spikes (often co-occurring with drift, due to model re-computation)
- Error rate >5% sustained over 10-minute window

## Root Cause

Usually caused by:
1. Data distribution shift in production inputs (seasonal, behavioral)
2. Incorrect model version deployed (wrong storageUri tag)
3. Feature engineering mismatch between training and serving pipeline

## Recovery Steps

1. Confirm drift signal from Arize: check `get-spans` for error_rate > 5% AND span attribute `drift_score > 0.3`
2. Identify the current model version: `kubectl get isvc demo-iris-2 -o yaml | grep storageUri`
3. Locate the previous stable model version in the GitOps repo (git log on inference-service.yaml)
4. Update `storageUri` in the InferenceService manifest to point to the previous stable model tag
5. Also verify resource limits are adequate for the rollback version (see RB-001 for CPU tuning)
6. Open a Merge Request with description: "chore(rollback): revert demo-iris-2 to stable model version"
7. HITL approval required — engineer reviews Arize drift report linked in MR description
8. After merge: ArgoCD syncs within 30s, KServe creates new revision, old revision terminates
9. Validate via Arize: error_rate returns to <1% within 5 minutes of new pod becoming Ready

## Validation

```bash
# Check InferenceService is Ready after rollback:
kubectl get isvc demo-iris-2 -n default
# READY: True, URL: populated

# Send known-good test case:
curl -sS -H "Content-Type: application/json" \
  -d '{"instances":[[5.1,3.5,1.4,0.2]]}' \  
  http://localhost:8082/v1/models/demo-iris-2:predict
# Expected: {"predictions":[0]} (Iris setosa)
```

## HITL Checkpoint

Agent must link the Arize drift report URL in the MR description.
Human must verify: (1) rollback target version, (2) Arize confirmation of drift signal.

## Related Runbooks

- RB-001: CPU Throttling (often co-occurring)
- RB-005: KServe Pod Not Ready — storageUri unreachable
- RB-010: ArgoCD ApplicationSet drift
