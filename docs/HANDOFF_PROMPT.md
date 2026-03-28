# Handoff Prompt (paste into a new chat if context is lost)

You are helping me maintain and extend **NeuroScale**, a self-service AI inference platform on Kubernetes with GitOps + Golden Path + guardrails.

Repo: `neuroscale-platform` (Windows, local k3d).

Key docs to read first:
- `docs/PROJECT_MEMORY.md`
- `plan-neuroScale.prompt.md`
- `README.md`

Current progress (all 6 milestones complete):
- Milestone A (GitOps drift self-heal) ✅ done.
- Milestone B (GitOps-managed KServe install + working endpoint) ✅ done.
- Milestone C (Backstage Golden Path template creates PR → merge → ArgoCD deploy → InferenceService Ready) ✅ done.
- Milestone D (Kyverno admission + CI policy simulation, CI false-green fixed) ✅ done.
- Milestone E (cost proxy PR comment, bootstrap script, visual smoke test) ✅ done.
- Milestone F (ApplicationSet, non-root policy, namespace quotas, OpenCost, multi-env Backstage, guest auth) ✅ done.

Remaining backlog:
- Restore kube-rbac-proxy sidecar in KServe controller with a verified reachable image mirror (currently removed; see docs/PROJECT_MEMORY.md section 7).

Constraints:
- Demo-first; minimize complexity; port-forward first; KServe simplest mode first; Kyverno first; CI must validate rendered Helm manifests.
