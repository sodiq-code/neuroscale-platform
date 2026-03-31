# Week 2 Learning Review — Milestone B (AI Serving Baseline)

## DoD check

- Done: Serving stack installation is GitOps-managed.
- Done: One InferenceService reached `Ready=True`.
- Done: One documented inference request returned predictions.

## System understanding (what runs what)

1. KServe watches InferenceService.
2. KServe creates Knative service/revision/route resources (serverless mode).
3. Knative networking uses Kourier to route requests.
4. Request reaches predictor container via Knative Host-based routing.

## Key failures and lessons

### Failure 1: ingress mismatch confusion
- Symptom: InferenceService stuck not ready / ingress not created.
- Cause: config expectations around Istio vs Kourier behavior in KServe ingress settings.
- Fix: use Kourier-compatible behavior (`disableIstioVirtualHost=true`) and validate readiness again.

### Failure 2: Argo comparison/apply instability
- Symptom: serving-stack app not syncing cleanly.
- Causes:
  - repo-server instability (`connection refused`).
  - duplicate/overlapping Knative CRD rendering path.
  - webhook/CRD mutation drift during apply.
- Fixes:
  - restart repo-server.
  - adjust serving-stack kustomization.
  - add precise Argo ignore-differences where runtime mutation is expected.

## Decisions made

- Standardize on Kourier for this local platform path.
- Keep versions pinned to observed working versions.
- Keep GitOps app-of-apps structure (`infrastructure/apps`) for clearer control-plane boundaries.

## Evidence

- Argo applications reached Synced/Healthy.
- Inference request through Kourier returned prediction payload.

## Interview-ready statement

"Week 2 showed production-style platform thinking: I didn’t stop at deploying KServe; I resolved real reconciliation and networking edge cases, then captured them as deterministic GitOps behavior with evidence."
