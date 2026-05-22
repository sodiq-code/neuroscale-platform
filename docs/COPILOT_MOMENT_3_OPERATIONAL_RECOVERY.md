# Copilot Moment 3: Operational Recovery — Making the Platform Operable Under Failure

## The Problem

During Kyverno installation, the ArgoCD repo-server entered `Unknown` state. All 7 applications showed `Unknown` sync and health status. The GitOps reconciliation loop was completely broken.

```
$ kubectl -n argocd get applications
NAME                       SYNC STATUS   HEALTH STATUS
neuroscale-infrastructure  Unknown        Unknown
serving-stack              Unknown        Unknown
policy-guardrails          Unknown        Unknown
backstage                  Unknown        Unknown
```

The error from ArgoCD:

```
Message: rpc error: code = Unavailable desc = connection refused
```

This was the second time the repo-server had crashed. The first was during initial bootstrap. The pattern was becoming a recurring operational risk.

## Where Copilot Helped

**The question I asked Copilot:**

> "ArgoCD repo-server keeps entering CrashLoopBackOff after adding new platform components. This is the second time. The first was during bootstrap, now it's during Kyverno install. I need: (1) the root cause pattern, (2) a deterministic recovery procedure, and (3) a prevention strategy I can document as a runbook."

**What Copilot helped me understand:**

1. **Root cause pattern:** Kyverno's webhook registration during initialization creates a window where all Kubernetes API mutations time out. ArgoCD's continuous sync loop hits this timeout, causing the repo-server to lose its gRPC connection and crash. This is a known interaction between admission webhooks and GitOps controllers on small clusters.

2. **Recovery procedure:**
```bash
# Step 1: Restart repo-server
kubectl -n argocd rollout restart deploy/argocd-repo-server

# Step 2: Wait for stability
kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=120s

# Step 3: Force hard refresh on stuck applications
kubectl -n argocd patch application neuroscale-infrastructure \
  --type merge \
  -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```

3. **Prevention strategy:**
- Deploy Kyverno before other components during bootstrap
- Use `webhookAnnotations` patch to suppress premature webhook registration
- Include repo-server health in the smoke test
- Document the recovery in an operational runbook

## The Result

From the runbook, recovery is now a 3-command, 2-minute procedure:

```bash
kubectl -n argocd rollout restart deploy/argocd-repo-server
kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=120s
kubectl -n argocd get applications
# All 7 applications: Synced/Healthy within 3 minutes
```

The failure is documented in:
- `docs/REALITY_CHECK_MILESTONE_1_GITOPS_SPINE.md` (first occurrence)
- `docs/REALITY_CHECK_MILESTONE_4_GUARDRAILS.md` (Kyverno-triggered recurrence)
- `docs/runbook.md` (operational recovery procedure)

## Why This Shows Judgment, Not Just Code Generation

Copilot didn't just help fix a crash. It helped me:

- **Identify a recurring pattern** across two seemingly different failures (bootstrap vs Kyverno install)
- **Build a deterministic runbook** that any operator can follow
- **Implement prevention** (webhook annotations, component ordering) that stops the failure from recurring
- **Document the operational knowledge** so it survives beyond the original engineer

This is Day-2 operations maturity. The platform doesn't just work — it's recoverable when things go wrong, and the recovery procedure is documented and repeatable.

**"The platform became operable under failure."**
