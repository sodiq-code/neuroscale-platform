# ArgoCD Sync Recovery — Runbook #7

**Tags:** argocd, sync, unknown, reconciliation, gitops
**Severity:** P2 — GitOps enforcement paused during outage window
**Date documented:** 2025-01-08 (Hermes Agent GEPA loop — Skill Document)

## Problem Description

ArgoCD applications enter `Unknown` sync/health state. The GitOps reconciliation loop
stops enforcing desired state. This means drift can accumulate undetected.

## Common Causes

1. repo-server CrashLoopBackOff (most common)
2. Kyverno webhook initializing (causes API server timeouts)
3. Git repository unreachable (network / credentials)
4. Resource pressure causing controller eviction

## Recovery Steps

1. Identify failing component:
   - `kubectl -n argocd get pods`
   - Look for: CrashLoopBackOff, 0/1 Ready, OOMKilled
2. Restart repo-server (covers 80% of cases):
   - `kubectl -n argocd rollout restart deploy/argocd-repo-server`
   - `kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=120s`
3. Force hard refresh on all stuck applications:
   - `kubectl -n argocd patch application <name> --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'`
4. If Kyverno is the cause: wait 2-3 minutes for webhook initialization, then retry
5. Verify all applications return to Synced/Healthy within 5 minutes

## Automated Detection Signal

Agent detects ArgoCD degradation when:
- Arize Phoenix shows inference latency spike (ArgoCD sync failure → manifest drift → resource contention)
- `kubectl get applications -n argocd` returns any app in Degraded/Unknown state

## HITL Note

ArgoCD restart does not modify application state — safe to execute without human approval.
Recovery is deterministic and reversible.

## Verification

```bash
kubectl -n argocd get applications
# All should show: SYNC STATUS = Synced, HEALTH = Healthy
```
