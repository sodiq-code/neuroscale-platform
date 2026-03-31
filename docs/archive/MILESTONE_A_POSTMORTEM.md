# Milestone A Postmortem — GitOps Spine

## Outcome

- ArgoCD manages platform and app resources from git.
- Drift self-heal demonstrated: deleting `nginx-test` triggers automatic recreation within 20 seconds.
- Repo and docs shifted to milestone framing.

## Architecture: GitOps Reconciliation Contract and Desired-State Convergence

GitOps is a reconciliation contract: desired state in git continuously converges live state in cluster.
This removes snowflake drift and turns rollback into a git revert + reconcile operation.

## Incident: ArgoCD repo-server CrashLoopBackOff Misdiagnosed as Manifest Error

- **Symptom:** Argo repo-server became unhealthy (`Unknown`), causing sync/comparison instability.
- **Root cause:** Controller dependency outage — not a manifest correctness problem.
- **Fix:** Restart repo-server pod and validate recovery.
- **Prevention:** Include repo-server health checks in troubleshooting runbook.

## Design Decisions

- Keep app-of-apps direction for modular blast radius and independent sync boundaries.
- Pin test image tags (no `:latest`) to prepare for policy guardrails.

## Evidence

- ArgoCD applications healthy after reconciliation.
- Drift demo reproducible: delete workload → auto recreation confirmed.
