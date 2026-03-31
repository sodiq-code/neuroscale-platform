# Handoff Prompt (paste into a new chat if context is lost)

You are helping me build **NeuroScale**, a self-service AI inference platform on Kubernetes with GitOps + Golden Path + guardrails.

Repo: `neuroscale-platform` (Windows, local k3d).

Key docs to read first:
- `docs/PROJECT_MEMORY.md`
- `plan-neuroScale.prompt.md`
- `README.md`

Current progress:
- Milestone A (GitOps drift self-heal) is done.
- Milestone B (GitOps-managed serving stack + working endpoint) is done.
- Next task: Milestone C (Backstage Golden Path template that creates PRs for new model apps).

Constraints:
- Demo-first; minimize complexity; port-forward first; KServe simplest mode first; Kyverno first; CI must validate rendered Helm manifests.

Please propose the next 3–5 concrete repo changes (files to add/modify) to complete Milestone C and how to verify success.
