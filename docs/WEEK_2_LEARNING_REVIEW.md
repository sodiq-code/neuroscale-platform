# Week 2 Learning Review — Milestone B (AI Serving Baseline)

## Milestone B DoD: KServe AI Serving Baseline — GitOps-Managed Install and Verified Inference Endpoint

- Done: Serving stack installation is GitOps-managed.
- Done: One InferenceService reached `Ready=True`.
- Done: One documented inference request returned predictions.

## System Understanding: KServe → Knative → Kourier Request Path for Serverless Inference

1. KServe watches InferenceService.
2. KServe creates Knative service/revision/route resources (serverless mode).
3. Knative networking uses Kourier to route requests.
4. Request reaches predictor container via Knative Host-based routing.

## Key Failures and Lessons

### Failure 1: InferenceService Stuck Not Ready — KServe Default Config Assumes Istio, Incompatible with Kourier
- Symptom: InferenceService stuck not ready / ingress not created.
- Cause: config expectations around Istio vs Kourier behavior in KServe ingress settings.
- Fix: use Kourier-compatible behavior (`disableIstioVirtualHost=true`) and validate readiness again.

### Failure 2: ArgoCD Serving-Stack Sync Instability — repo-server Outage and Duplicate Knative CRD Rendering
- Symptom: serving-stack app not syncing cleanly.
- Causes:
  - repo-server instability (`connection refused`).
  - duplicate/overlapping Knative CRD rendering path.
  - webhook/CRD mutation drift during apply.
- Fixes:
  - restart repo-server.
  - adjust serving-stack kustomization.
  - add precise Argo ignore-differences where runtime mutation is expected.

## Design Decisions: Standardize on Kourier, Pin Versions, Preserve App-of-Apps Structure

- Standardize on Kourier for this local platform path.
- Keep versions pinned to observed working versions.
- Keep GitOps app-of-apps structure (`infrastructure/apps`) for clearer control-plane boundaries.

## Evidence: Argo Applications Synced/Healthy, Inference Request Returns Prediction Payload

- Argo applications reached Synced/Healthy.
- Inference request through Kourier returned prediction payload.

## Interview-Ready Statement

"Week 2 showed production-style platform thinking: I didn’t stop at deploying KServe; I resolved real reconciliation and networking edge cases, then captured them as deterministic GitOps behavior with evidence."
