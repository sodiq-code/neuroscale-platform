# Project Memory — NeuroScale

This file is the single source of truth for **current decisions, progress, and demo contracts**.

## 1) One-sentence pitch
NeuroScale is a self-service AI inference platform on Kubernetes: developers ship model endpoints through a Golden Path, while the platform enforces drift control (GitOps), guardrails (policy-as-code), and cost attribution primitives by default.

## 2) North Star demo (must always work)
Click template (Backstage) → PR created → merge → ArgoCD sync → KServe InferenceService live → intentional bad change is blocked (CI + admission).

## 3) Current status
- Milestone A — GitOps spine (drift control proven): ✅ DONE
- Milestone B — AI serving baseline (GitOps-managed KServe install + one endpoint verified): ✅ DONE
- Milestone C — Golden Path (Backstage creates PR → merge → Argo deploy): ✅ DONE
- Milestone D — Guardrails (CI + admission policies block unsafe changes): ✅ DONE

## 4) Key repo files (anchors)
- GitOps root app: bootstrap/root-app.yaml
- Backstage app (ArgoCD): infrastructure/apps/backstage-app.yaml
- Test app (ArgoCD): infrastructure/apps/test-app-app.yaml
- Test workload: apps/test-app/deployment.yaml
- Example inference service: apps/ai-model-alpha/inference-service.yaml
- Golden Path output: apps/demo-iris-2/inference-service.yaml
- KServe runtime example: infrastructure/kserve/sklearn-runtime.yaml
- Backstage incident RCA (learning → prevention): infrastructure/INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md
- Execution plan + interview script: plan-neuroScale.prompt.md

## 5) Decisions (keep these stable unless explicitly changed)
- Demo-first: prioritize a reliable, repeatable demo loop over extra realism.
- Local access: port-forward first; ingress/TLS later.
- KServe: serverless mode with Kourier (not Istio); disableIstioVirtualHost=true.
- Policies: Kyverno first; OPA later as an optional breadth upgrade.
- CI principle: render Helm → validate schemas → policy test on rendered manifests.
- Label convention: kebab-case for Kubernetes labels (cost-center, not costCenter).

## 6) Evidence checklist (capture every milestone)
### Milestone A evidence
- ArgoCD Applications list showing `neuroscale-infrastructure` + `test-app` as Synced/Healthy.
- Terminal showing GitOps self-heal: delete `nginx-test` then it reappears.

### Milestone B evidence
- `InferenceService` Ready + a successful inference request.
- ArgoCD showing the KServe install layer is GitOps-managed.

### Milestone C evidence
- Backstage template visible and runnable at /create.
- Scaffolder run opens PR with apps/demo-iris-2/ and infrastructure/apps/demo-iris-2-app.yaml.
- PR merge triggers ArgoCD child app creation and sync.
- InferenceService/demo-iris-2 reaches Ready=True.
- Prediction returns {"predictions":[1,1]}.

### Milestone D evidence
- kubectl apply of InferenceService without required labels is denied by Kyverno.
- CI policy simulation fails for non-compliant manifests before merge.
- Compliant manifests pass both CI and admission.

## 7) Known landmines + pivots
- kube-rbac-proxy image (gcr.io/kubebuilder/) is inaccessible; sidecar is removed in serving-stack patch.
- Backstage dangerouslyDisableDefaultAuthPolicy=true is local-only; must be replaced with auth provider for production.
- remove-inferenceservice-crd.yaml is a Kustomize patch (build-time only) — NEVER apply directly with kubectl.
- Kyverno install can disrupt ArgoCD sync loop during initialization window; use webhookAnnotations patch.
- Label key: always use cost-center (hyphen), not costCenter (camelCase).

## 8) Reality Check documentation (what actually failed)
- Milestone A failures: docs/REALITY_CHECK_MILESTONE_1_GITOPS_SPINE.md
- Milestone B failures: docs/REALITY_CHECK_MILESTONE_2_KSERVE_SERVING.md
- Milestone C failures: docs/REALITY_CHECK_MILESTONE_3_GOLDEN_PATH.md
- Milestone D failures: docs/REALITY_CHECK_MILESTONE_4_GUARDRAILS.md

## 9) Post-Milestone D backlog (hardening for production parity)
1. Replace dangerouslyDisableDefaultAuthPolicy with a real Backstage auth provider.
2. Restore kube-rbac-proxy with a verified reachable image mirror.
3. Enforce strict branch protection with no personal bypass on main.
4. Add synthetic smoke test: run Backstage template and verify InferenceService readiness automatically.
5. Add OpenCost/Kubecost-style showback dashboards once labels and bounds are enforced.
6. Add Terraform-managed cloud resources + Infracost PR cost estimates for IaC.
7. Add separate values profiles (dev, staging, prod) with explicit probe defaults.
