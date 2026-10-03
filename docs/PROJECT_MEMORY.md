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
- Milestone E — Cost proxy + portability (resource-delta PR comment, bootstrap script, visual smoke test, CI false-green fixed): ✅ DONE
- Milestone F — Production hardening (ApplicationSet, non-root policy, namespace quotas, OpenCost, multi-env Backstage, guest auth): ✅ DONE

## 4) Key repo files (anchors)
- GitOps root app: bootstrap/root-app.yaml
- Backstage app (ArgoCD): infrastructure/apps/backstage-app.yaml
- ApplicationSet (auto-discovers apps/*): infrastructure/apps/model-endpoints-appset.yaml
- Test workload: apps/test-app/deployment.yaml
- Example inference service: apps/ai-model-alpha/inference-service.yaml
- Golden Path output: apps/demo-iris-2/inference-service.yaml
- KServe runtime example: infrastructure/kserve/sklearn-runtime.yaml
- Backstage incident RCA (learning → prevention): infrastructure/INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md
- Execution plan + interview script: plan-neuroScale.prompt.md
- Bootstrap script (first-time cluster setup): scripts/bootstrap.sh
- Smoke test (visual end-to-end verification): scripts/smoke-test.sh
- Port-forward helper (all UIs in one command): scripts/port-forward-all.sh
- CI workflow (schema + policy + cost proxy): .github/workflows/guardrails-checks.yaml
- Namespace quotas + limits: infrastructure/namespaces/default/{resource-quota,limit-range}.yaml
- OpenCost Helm chart: infrastructure/opencost/{Chart.yaml,values.yaml}
- Backstage dev values: infrastructure/backstage/values.yaml
- Backstage prod values (GitHub OAuth, HA): infrastructure/backstage/values-prod.yaml
- Cloud promotion guide (EKS/GKE Terraform, DNS, TLS): docs/CLOUD_PROMOTION_GUIDE.md

## 5) Decisions (keep these stable unless explicitly changed)
- Demo-first: prioritize a reliable, repeatable demo loop over extra realism.
- Local access: port-forward first; ingress/TLS later.
- KServe: serverless mode with Kourier (not Istio); disableIstioVirtualHost=true.
- Policies: Kyverno first; OPA later as an optional breadth upgrade.
- CI principle: render Helm → validate schemas → policy test on rendered manifests.
- Label convention: kebab-case for Kubernetes labels (cost-center, not costCenter).

## 6) Evidence checklist (capture every milestone)
### Milestone A evidence
- ArgoCD Applications list showing `neuroscale-infrastructure` as Synced/Healthy, plus model-endpoint child apps created by ApplicationSet.
- Terminal showing GitOps self-heal: delete `nginx-test` then it reappears within ~20 s.

### Milestone B evidence
- `InferenceService` Ready + a successful inference request.
- ArgoCD showing the KServe install layer is GitOps-managed.

### Milestone C evidence
- Backstage template visible and runnable at /create.
- Scaffolder run opens PR with apps/demo-iris-2/ folder.
- ApplicationSet detects new folder → creates child Application → sync.
- InferenceService/demo-iris-2 reaches Ready=True.
- Prediction returns {"predictions":[1,1]}.

### Milestone D evidence
- kubectl apply of InferenceService without required labels is denied by Kyverno.
- CI policy simulation fails for non-compliant manifests before merge.
- Compliant manifests pass both CI and admission.

### Milestone F evidence
- `neuroscale-model-endpoints` ApplicationSet exists and generates Applications for every folder under apps/.
- `default-namespace-quota` ResourceQuota and `default-namespace-limits` LimitRange exist in default namespace.
- 5 ClusterPolicies installed (includes disallow-root-containers).
- OpenCost deployment healthy in namespace `opencost`.
- Backstage auth uses guest provider (no dangerouslyDisableDefaultAuthPolicy in logs).

## 7) Known landmines + pivots
- kube-rbac-proxy image (gcr.io/kubebuilder/) is inaccessible; sidecar is removed in serving-stack patch.
- Backstage: dev profile uses guest auth provider (dangerouslyAllowOutsideDevelopment: true). For production, use values-prod.yaml which configures GitHub OAuth instead.
- remove-inferenceservice-crd.yaml is a Kustomize patch (build-time only) — NEVER apply directly with kubectl.
- Kyverno install can disrupt ArgoCD sync loop during initialization window; use webhookAnnotations patch.
- Label key: always use cost-center (hyphen), not costCenter (camelCase).
- Per-app Application files (ai-model-alpha-app.yaml, demo-iris-2-app.yaml, test-app-app.yaml) were replaced by model-endpoints-appset.yaml in Milestone F — do not recreate those individual files.
- ~~Golden Path scaffolder template still generates infrastructure/apps/<name>-app.yaml~~ — **FIXED**: skeleton file removed; template now only writes apps/<name>/inference-service.yaml and the ApplicationSet auto-discovers it.

## 8) Reality Check documentation (what actually failed)
- Milestone A failures: docs/REALITY_CHECK_MILESTONE_1_GITOPS_SPINE.md
- Milestone B failures: docs/REALITY_CHECK_MILESTONE_2_KSERVE_SERVING.md
- Milestone C failures: docs/REALITY_CHECK_MILESTONE_3_GOLDEN_PATH.md
- Milestone D failures: docs/REALITY_CHECK_MILESTONE_4_GUARDRAILS.md
- Milestone E design decisions: docs/REALITY_CHECK_MILESTONE_5_COST_PROXY.md
- Milestone F design decisions: docs/REALITY_CHECK_MILESTONE_6_PRODUCTION_HARDENING.md

## 9) Post-Milestone E hardening (all items implemented in this session)
1. ✅ Replace dangerouslyDisableDefaultAuthPolicy with proper guest auth provider (values.yaml).
2. ⏳ Restore kube-rbac-proxy with a verified reachable image mirror (still pending — image inaccessible).
3. ✅ Enforce strict branch protection (GitHub UI: Settings → Branches → main → enable "Require status checks", disable "Allow bypasses" and "Allow force pushes").
4. ✅ Separate values profiles (dev=values.yaml, prod=values-prod.yaml) with explicit probe defaults.
5. ✅ OpenCost/Kubecost-style showback deployed as GitOps-managed infrastructure (infrastructure/opencost/).
6. ✅ ApplicationSet: single neuroscale-model-endpoints ApplicationSet auto-discovers apps/* directories (replaces per-app Application files).
7. ✅ Namespace ResourceQuota + LimitRange for default namespace (infrastructure/namespaces/default/).
8. ✅ Baseline security Kyverno policy: disallow-root-containers enforces runAsNonRoot on all Deployments in default namespace.

## 10) Post-Milestone F clean-up (closed backlog items)
1. ✅ Backstage scaffolder template aligned with ApplicationSet: removed `infrastructure/apps/<name>-app.yaml` from skeleton; PR body now correctly describes only `apps/<name>/inference-service.yaml`.
2. ✅ Cloud promotion story documented: docs/CLOUD_PROMOTION_GUIDE.md covers EKS/GKE Terraform, ingress swap, DNS, TLS (cert-manager + ACM), production Backstage, and OpenCost billing integration.

## 11) Key new files added in post-milestone hardening
- ApplicationSet: infrastructure/apps/model-endpoints-appset.yaml
- Non-root policy: infrastructure/kyverno/policies/disallow-root-containers.yaml
- Namespace quotas: infrastructure/namespaces/default/{resource-quota,limit-range,kustomization}.yaml
- Namespace resources app: infrastructure/apps/default-namespace-resources-app.yaml
- OpenCost chart: infrastructure/opencost/{Chart.yaml,values.yaml}
- OpenCost app: infrastructure/apps/opencost-app.yaml
- Backstage prod profile: infrastructure/backstage/values-prod.yaml
- Cloud promotion guide: docs/CLOUD_PROMOTION_GUIDE.md
