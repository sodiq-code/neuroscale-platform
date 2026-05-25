# Kyverno Policy Denial Debugging — Runbook #9

**Tags:** kyverno, admission, policy, denial, guardrails
**Severity:** P3 — blocks deployment but protects cluster integrity
**Date documented:** 2025-02-14 (Hermes Agent GEPA loop — Skill Document)

## Problem Description

A Kubernetes resource create/update is rejected by Kyverno admission webhook with:
`admission webhook "validate.kyverno.svc-fail" denied the request`

## NeuroScale Enforced Policies (5 ClusterPolicies)

| Policy | Blocks |
|--------|--------|
| require-standard-labels-inferenceservice | ISVC without owner/cost-center labels |
| require-standard-labels-deployment | Deployment without owner/cost-center labels |
| require-resource-requests-limits | Container without cpu/memory requests+limits |
| disallow-latest-image-tag | Container using :latest image tag |
| disallow-root-containers | Container without runAsNonRoot: true |

## Recovery Steps

1. Read the full denial message: `kubectl describe isvc <name>` or from kubectl output
2. Identify which policy triggered: look for policy name in error message
3. Add the missing field to the manifest:
   - Labels: add `owner: <team>` and `cost-center: cc-<code>` under `metadata.labels`
   - Resources: add `resources.requests.cpu` and `resources.requests.memory` under each container
   - Image tag: change `:latest` to a pinned semver tag (e.g., `:v0.12.1`)
   - Root containers: add `securityContext.runAsNonRoot: true` under container spec
4. Validate locally before committing: `kyverno-cli apply policies/ --resource manifest.yaml`
5. Open a compliant MR — CI kyverno-cli simulation will catch violations before merge

## HITL Note

Policy denials are a FEATURE not a bug. The autonomous agent MUST NOT attempt to
disable or bypass Kyverno to unblock a deployment. If the agent generates a manifest
that violates policy, it must fix the manifest, not the policy.

## Agent Self-Correction Protocol

When the Operator Agent generates a YAML fix that would be denied by Kyverno:
1. Parse the denial error from dry-run output
2. Identify the missing field
3. Regenerate the manifest with the correction applied
4. Re-validate before committing the MR

## Verification

```bash
# Test policy enforcement directly:
kubectl apply --dry-run=server -f apps/demo-iris-2/inference-service.yaml
# Should succeed with: configured (dry run)

# Confirm policies are active:
kubectl get clusterpolicies
# Should show 5 policies, all Ready
```
