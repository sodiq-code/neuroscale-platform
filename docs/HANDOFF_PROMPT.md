# Handoff Prompt (paste into a new chat if context is lost)

You are helping me build **NeuroScale**, a self-service AI inference platform on Kubernetes with GitOps + Golden Path + guardrails.

Repo: `neuroscale-platform` (Windows, local k3d).

Key docs to read first:
- `docs/PROJECT_MEMORY.md`
- `plan-neuroScale.prompt.md`
- `README.md`

Current progress:
- Milestone A (GitOps drift self-heal) is done.
- Next task: Milestone B (make KServe install GitOps-managed in this repo; verify one working inference endpoint).

Constraints:
- Demo-first; minimize complexity; port-forward first; KServe simplest mode first; Kyverno first; CI must validate rendered Helm manifests.

Please propose the next 3–5 concrete repo changes (files to add/modify) to complete Milestone B and how to verify success.
