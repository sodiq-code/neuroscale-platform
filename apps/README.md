## Apps

Workloads in this folder are deployed by the `neuroscale-model-endpoints` ArgoCD
ApplicationSet. The ApplicationSet automatically discovers every directory added
here and creates a child Application — no manual registration required.

Current app manifests:

- `apps/test-app/` — simple workload for GitOps self-heal demo
- `apps/ai-model-alpha/` — sample KServe `InferenceService` (Milestone B)
- `apps/demo-iris-2/` — Golden Path output created via Backstage scaffolder (Milestone C)
