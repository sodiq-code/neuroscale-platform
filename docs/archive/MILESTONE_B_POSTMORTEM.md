# Milestone B Postmortem — AI Serving Baseline

## Outcome

- Serving stack installation is GitOps-managed.
- One `InferenceService` reached `Ready=True`.
- One documented inference request returned a valid prediction payload.

## Architecture: KServe → Knative → Kourier Request Path

1. KServe watches `InferenceService`.
2. KServe creates Knative service/revision/route resources (serverless mode).
3. Knative networking uses Kourier to route requests.
4. Request reaches predictor container via Knative host-based routing.

## Incident 1: InferenceService Stuck Not Ready — Istio/Kourier Ingress Mismatch

- **Symptom:** `InferenceService` stuck not ready; ingress not created.
- **Root cause:** KServe default config assumes Istio; incompatible with Kourier behavior.
- **Fix:** Set `disableIstioVirtualHost=true` and revalidate readiness.

## Incident 2: Serving-Stack Sync Instability — repo-server Outage and Duplicate Knative CRD Rendering

- **Symptom:** Serving-stack ArgoCD app not syncing cleanly.
- **Root causes:**
  - repo-server instability (`connection refused`).
  - Duplicate/overlapping Knative CRD rendering path.
  - Webhook/CRD mutation drift during apply.
- **Fixes:**
  - Restart repo-server.
  - Adjust serving-stack kustomization to eliminate duplicate CRD path.
  - Add precise `ignoreDifferences` entries where runtime mutation is expected.

## Design Decisions

- Standardize on Kourier for this platform path (no Istio dependency).
- Keep versions pinned to observed working versions.
- Keep GitOps app-of-apps structure (`infrastructure/apps`) for clearer control-plane boundaries.

## Evidence

- ArgoCD applications reached Synced/Healthy.
- Inference request through Kourier returned prediction payload.
