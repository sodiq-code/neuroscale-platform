# Week 1 Learning Review — Milestone A (GitOps Spine)

## DoD check

- Done: ArgoCD manages platform/app resources from git.
- Done: Drift self-heal demonstrated by deleting `nginx-test` and observing recreation.
- Done: Repo/docs shifted from tutorial framing to milestone framing.

## What this week taught

### Concept
GitOps is a reconciliation contract: desired state in git continuously converges live state in cluster.

### Why this matters
It removes snowflake drift and turns rollback into git revert + reconcile.

## Debugging narrative

- Failure: Argo repo-server became unhealthy (`Unknown`), causing sync/comparison instability.
- Root cause: controller dependency outage, not manifest correctness.
- Fix: restart repo-server pod and validate recovery.
- Prevention: include repo-server health checks in troubleshooting runbook.

## Decisions

- Decision: keep app-of-apps direction for modular blast radius and independent sync boundaries.
- Decision: pin test image tag (no `:latest`) to prepare for policy guardrails.

## Evidence

- Argo applications healthy after reconciliation.
- Drift demo: delete workload -> auto recreation.

## Interview-ready statement

"Week 1 proved platform reliability fundamentals: GitOps as source of truth, drift correction, and deterministic app deployment from repository state."
