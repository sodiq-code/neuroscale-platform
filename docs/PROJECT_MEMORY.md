# Project Memory — NeuroScale

This file is the single source of truth for **current decisions, progress, and demo contracts**.

## 1) One-sentence pitch
NeuroScale is a self-service AI inference platform on Kubernetes: developers ship model endpoints through a Golden Path, while the platform enforces drift control (GitOps), guardrails (policy-as-code), and cost attribution primitives by default.

## 2) North Star demo (must always work)
Click template (Backstage) → PR created → merge → ArgoCD sync → KServe InferenceService live → intentional bad change is blocked (CI + admission).

## 3) Current status
- Milestone A — GitOps spine (drift control proven): ✅ DONE
- Milestone B — AI serving baseline (GitOps-managed KServe install + one endpoint verified): 🟡 NEXT
- Milestone C — Golden Path (Backstage creates PR → merge → Argo deploy): ⏳ PLANNED
- Milestone D — Guardrails (CI + admission policies block unsafe changes): ⏳ PLANNED

## 4) Key repo files (anchors)
- GitOps root app: bootstrap/root-app.yaml
- Backstage app (ArgoCD): infrastructure/apps/backstage-app.yaml
- Test app (ArgoCD): infrastructure/apps/test-app-app.yaml
- Test workload: apps/test-app/deployment.yaml
- Example inference service: apps/ai-model-alpha/inference-service.yaml
- KServe runtime example: infrastructure/kserve/sklearn-runtime.yaml
- Backstage incident RCA (learning → prevention): infrastructure/INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md
- Execution plan + interview script: plan-neuroScale.prompt.md

## 5) Decisions (keep these stable unless explicitly changed)
- Demo-first: prioritize a reliable, repeatable demo loop over extra realism.
- Local access: port-forward first; ingress/TLS later.
- KServe: start with simplest reliable mode on local k3d; add Knative/Kourier later for scale-to-zero.
- Policies: Kyverno first; OPA later as an optional breadth upgrade.
- CI principle: render Helm → validate schemas → policy test on rendered manifests.

## 6) Evidence checklist (capture every milestone)
### Milestone A evidence
- ArgoCD Applications list showing `neuroscale-infrastructure` + `test-app` as Synced/Healthy.
- Terminal showing GitOps self-heal: delete `nginx-test` then it reappears.

### Milestone B evidence (target)
- `InferenceService` Ready + a successful inference request.
- ArgoCD showing the KServe install layer is GitOps-managed.

## 7) Known landmines + pivots
- Laptop RAM wall (Istio/Knative/KServe + Backstage): use raw deployment first; temporarily scale down Backstage during Week 2 verification.
- Backstage GitHub auth: run an “auth smoke test” (minimal PR) before relying on full templates.
- CI Helm rendering: keep one deterministic script for render/validate/policy-test.
