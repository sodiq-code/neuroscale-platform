## Plan: NeuroScale “Golden Path” AI Platform (IDP + GitOps + Guardrails)

Build a **B2B SaaS-grade Internal Developer Platform** that lets a developer deploy an AI inference endpoint by clicking a Backstage template, while the platform enforces reliability, governance, and cost controls automatically. This directly targets the 2026 “pain rank” from your report: **Complexity (#1)** via golden paths, **Reliability/Drift (#2)** via GitOps + validation, **Cost/Waste (#3)** via preventative resource/cost guardrails, **Governance (#4)** via policy-as-code. The plan is optimized for **local k3d** (zero-cost) but is structured so it maps cleanly to EKS/GKE later.

**Timeline (Weeks 0–5)**
- **Week 0 (Half-day): Demo contract locked**
   - DoD: “North Star Demo” flow written + success screenshots list (Argo healthy, template run, KServe ready, policy fail)
- **Week 1: GitOps spine (apps + infra)**
   - DoD: ArgoCD manages infra + apps; drift self-heal demonstrated; at least one app under `apps/` deploys via GitOps
- **Week 2: KServe install + one working endpoint**
   - DoD: KServe install is GitOps-managed; one `InferenceService` reaches Ready; one documented test request returns a response
   - Pivot (if laptop RAM is tight): use KServe “raw deployment” style first (no scale-to-zero), and temporarily scale down Backstage during verification if needed
- **Week 3: Backstage Golden Path (solves “Empty Portal”)**
   - DoD: GitHub auth smoke test passes (Backstage can open a minimal PR); Backstage template creates a PR that adds a new `apps/<name>/` folder with a compliant `InferenceService`; merge → Argo deploys → endpoint becomes Ready
- **Week 4: Guardrails (Kyverno) + PR-time checks**
   - DoD: non-compliant changes fail in CI and are denied by admission; compliant changes pass and deploy
- **Week 5 (Optional): Cost proxy + hiring polish**
   - DoD: PR comment summarizes requested CPU/memory deltas; demo script + architecture doc + runbook exist

**Guiding Principles (to keep results outstanding)**
- Demo-first: if it doesn’t strengthen the click → PR → merge → deploy loop, it’s optional until later
- Stage complexity: make it work reliably first (raw deployment/port-forward), then add production parity (Knative/Ingress/TLS/OPA)
- Determinism: CI must render the exact manifests that would reach the cluster; avoid “it works on my machine” steps
- Evidence over claims: every feature should have a failing demo case and a passing demo case

**Repo Deliverables (Checklist)**
- [ ] `README` that explains: what this platform solves, quickstart, and the 3-minute demo flow
- [ ] “Demo script” doc (exact steps + expected outputs)
- [ ] Backstage scaffolder template: click → PR → merge → Argo deploy
- [ ] GitHub auth for scaffolder documented and demo-safe (GitHub App or fine-grained PAT) + credentials wired via Kubernetes Secret
- [ ] GitOps apps automation (ApplicationSet preferred) so new folders under `apps/` deploy automatically
- [ ] GitHub Actions PR checks:
   - [ ] `helm template` / rendered-manifest validation for charts
   - [ ] Kubernetes schema validation for YAML
   - [ ] Kyverno policy tests against rendered manifests
- [ ] One deterministic CI entrypoint script (render → validate → policy test) so failures are easy to debug
- [ ] Kyverno policy pack (owner/costCenter, requests/limits, deny `:latest`, baseline security)
- [ ] FinOps primitives (required labels + ResourceQuota/LimitRange + PR resource-delta “cost proxy” comment)
- [ ] KServe install layer captured in-repo and GitOps-managed (not “run this script manually”)
- [ ] Incident-proofing note tying the CI checks back to your RCA learnings

**Steps**
1. Define the “North Star Demo” and the artifacts you must be able to defend
   1. North Star flow (what you demo in 3 minutes): Backstage template → PR created → merge → ArgoCD sync → KServe InferenceService live → policy blocks bad config → PR checks prove correctness.
   2. Artifacts that make you senior-credible:
      - Architecture diagram (control plane vs data plane)
      - A runbook for deployment + rollback
      - A postmortem template + 1 “game day” drill scenario (you already have one real RCA in [infrastructure/INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md](infrastructure/INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md))
   3. What you must be able to explain on a whiteboard:
      - GitOps reconciliation loop (desired vs live state)
      - How “golden path” reduces cognitive load
      - Why PR-time checks + admission control prevents outages

2. Phase 1 — GitOps foundation (make the repo the source of truth)
   1. Confirm and document the GitOps topology you already have:
      - Root app-of-apps entry point in [bootstrap/root-app.yaml](bootstrap/root-app.yaml) (sync automated, prune, selfHeal)
      - Backstage child app in [infrastructure/backstage-app.yaml](infrastructure/backstage-app.yaml)
   2. Make the infrastructure directory “GitOps-ready” as it grows:
      - Establish a consistent pattern: every platform component has its own folder under infrastructure/ and (optionally) its own ArgoCD Application.
      - Keep cluster-scoped resources (CRDs, ClusterRoles, ClusterPolicies) explicit and separated to avoid accidental deletions (especially with `prune: true`).
   3. Add an “apps deployment” GitOps mechanism (this is the backbone for your demo):
      - Preferred: an ArgoCD ApplicationSet that generates an Application per app folder under apps/ (so the platform scales to “hundreds of services” without manual YAML).
      - Minimal fallback: a single ArgoCD Application that syncs apps/ as a directory (works but less realistic at scale).
   4. Interview defense points:
      - Why app-of-apps: isolates blast radius, allows independent sync/rollback, keeps infra modular.
      - Why automated sync + selfHeal: reduces drift; Git becomes the audit log.

3. Phase 2 — AI serving baseline (KServe as the standardized data plane)
   1. Make KServe installation and dependencies explicit (right now you only have runtime + example service):
      - Note: KServe installation is missing today in this repo; it must be GitOps-managed so CRDs/controllers exist before applying cluster-scoped runtimes and `InferenceService` resources.
      - Start with the simplest reliable KServe mode for local k3d (focus on a working endpoint first); add Knative + Kourier later if you want true scale-to-zero/serverless behavior.
      - Add a clear “KServe install” layer (Istio/Knative/KServe) as GitOps-managed infrastructure.
      - Ensure CRDs exist before applying [infrastructure/kserve/sklearn-runtime.yaml](infrastructure/kserve/sklearn-runtime.yaml).
   2. Keep your CPU-friendly serving path (important for zero-cost demos):
      - Runtime: [infrastructure/kserve/sklearn-runtime.yaml](infrastructure/kserve/sklearn-runtime.yaml)
      - Example service: [apps/ai-model-alpha/inference-service.yaml](apps/ai-model-alpha/inference-service.yaml)
      - Local demo reliability note: if a `storageUri` depends on external cloud storage (e.g., `gs://...`), be ready to switch to a local-friendly artifact source so your demo doesn’t fail due to egress/auth.
   3. Make networking deterministic for demo:
      - Decide one supported access method for inference (port-forward vs Ingress) and document it.
      - If using Ingress later, fill infrastructure/nginx-ingress/ and optionally infrastructure/cert-manager/ (currently empty) to show production parity.
   4. Interview defense points:
      - Why KServe over “Flask in a pod”: standardized inference API, scale-to-zero patterns, consistent runtime behavior.
      - Reliability story: isolate runtimes, set requests/limits, define readiness/liveness expectations.

4. Phase 3 — Backstage as the “product layer” (turn portal into an action engine, not a wiki)
   1. Stabilize and explain the Backstage deployment you already have:
      - Backstage is deployed via ArgoCD from [infrastructure/backstage-app.yaml](infrastructure/backstage-app.yaml)
      - Helm chart wrapper in [infrastructure/backstage](infrastructure/backstage) with values in [infrastructure/backstage/values.yaml](infrastructure/backstage/values.yaml)
      - Use your incident learnings as part of the system design (“we validate rendered manifests to prevent mis-nested Helm values regressions”).
   2. Implement the single most valuable Backstage capability: a scaffolder “Golden Path” template
      - Template goal: create a new app folder under apps/ with:
        - KServe InferenceService YAML (like [apps/ai-model-alpha/inference-service.yaml](apps/ai-model-alpha/inference-service.yaml))
        - Required labels/annotations (owner, costCenter, etc.)
        - Resource requests/limits (so cost + reliability guardrails have inputs)
      - Scaffolder workflow: click template → opens PR to this repo (you chose same-repo flow) → merge triggers ArgoCD to deploy.
   3. Make Backstage adoption “not empty portal” by design:
      - The portal must expose at least one self-service action that results in production change (the PR).
      - Add a small “service catalog” concept so ownership is first-class (ties directly to cost attribution + policy).
   4. Interview defense points:
      - Backstage isn’t the platform; it’s the UI for platform capabilities.
      - “Golden path” is a product: you measure adoption, reduce onboarding time, prevent footguns.

5. Phase 4 — Guardrails that enforce (Kyverno now, OPA later)
   1. Admission-time enforcement with Kyverno (primary)
      - Policies to implement first (high ROI, directly tied to your report + real incidents):
        - Require `owner` and `costCenter` labels on workloads and InferenceServices
        - Require requests/limits for CPU/memory
        - Deny floating image tags like `:latest`
        - Baseline security posture (non-root, drop capabilities where applicable)
      - Create a clear “policy library” location (e.g., a new infrastructure/kyverno/ or policies/ directory) and have ArgoCD apply it.
   2. PR-time enforcement in CI (GitHub Actions)
      - Render + validate what will actually hit the cluster:
            - CI must render Helm and validate the final rendered manifests (this is the direct prevention of your Backstage values nesting issue from the RCA)
            - `helm template` for charts (validate what will *actually* be applied, not just values files)
        - Schema validation (Kubernetes YAML correctness)
        - Policy simulation: run Kyverno tests against the rendered manifests
      - Outcome: “Syntactic success ≠ operational success” becomes a solved problem in your repo.
   3. Cost controls (preventative, not just dashboards)
      - Enforce that every workload declares requests/limits (so cost is attributable).
      - Add a PR comment that summarizes deltas in requested CPU/memory (a lightweight “cost proxy” that works even without Terraform).
      - Optional “showback” (later): deploy OpenCost/Kubecost-like tooling for visibility; keep enforcement in policy/CI.

         **FinOps implementation (staged)**
         - Stage 1 (now, Kubernetes-first):
            - Attribution primitives: require `owner`, `team`, `costCenter`, `env` labels (Kyverno)
            - Preventative bounds: require requests/limits + apply namespace `ResourceQuota`/`LimitRange`
            - PR visibility: comment on resource deltas and fail PRs that violate policy
         - Stage 2 (later, visibility): add OpenCost/Kubecost-style showback dashboards once labels and bounds are enforced
         - Stage 3 (later, IaC/cloud): add Terraform-managed cloud resources + Infracost PR cost estimates (Infracost is strongest when costed resources are expressed as IaC)
   4. OPA later (secondary spike)
      - Add OPA/Gatekeeper as a second policy engine only after Kyverno is solid, and use it where it wins (multi-domain policy like Terraform/Envoy, or orgs that standardize on Rego).
   5. Interview defense points:
      - “Shift left” (CI) + “shift down” (admission) together: CI catches issues early; admission prevents bypasses.
      - This is how regulated teams scale governance without human review bottlenecks.

6. Phase 5 — Prove it’s production thinking (operability + evidence)
   1. Reliability proof pack
      - A minimal on-call runbook for: “model not responding”, “Argo out of sync”, “Backstage down”, “policy blocking deploy”
      - A rollback story: revert PR → Argo reconciles → system returns to last known good.
   2. One intentional “failure demo” (this is what makes interviews memorable)
      - Example: try to deploy an InferenceService without `owner` label → Kyverno denies → CI also fails in PR.
      - Example: use `:latest` image tag → blocked.
   3. Tie to your existing real-world learning
      - Use [infrastructure/INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md](infrastructure/INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md) as evidence you understand platform incidents and prevention, not just happy-path installs.

**Verification**
- GitOps: ArgoCD shows all Applications healthy; deleting a resource manually gets reverted (selfHeal) from [bootstrap/root-app.yaml](bootstrap/root-app.yaml).
- Backstage: portal is reachable (port-forward or ingress) and can create a PR that adds a new app directory under apps/.
- Deployment: after merge, ArgoCD syncs and the new KServe InferenceService becomes ready; inference responds to a test request.
- Guardrails:
  - PR checks fail for invalid/missing labels or missing requests/limits.
  - Cluster admission blocks direct `kubectl apply` of non-compliant manifests.
- Cost proxy: PR comment shows requested CPU/memory deltas and flags “high request” changes.

**Decisions**
- Same-repo scaffolder PR flow (simplest and strongest demo loop)
- Default environment is local k3d/k3s (zero-cost, repeatable)
- Policy engines: Kyverno first, OPA later for breadth
- CI system: GitHub Actions for PR-time validation and visibility

## Interview Script (5–7 minutes)

Use this as your default “walk me through your project” answer. The goal is to tell a story that maps directly to the 2026 pain signals: complexity (#1), drift/reliability (#2), cost (#3), governance (#4).

**0:00–0:30 — One-sentence pitch + outcomes**
- “NeuroScale is a self-service AI inference platform on Kubernetes. Developers deploy a model endpoint through a Backstage Golden Path, and the platform enforces reliability, governance, and cost controls via GitOps, CI validation, and admission policies.”
- “The demo is: click template → PR → merge → Argo deploy → KServe endpoint live. Then I intentionally submit a bad change and show it gets blocked.”

**0:30–1:45 — GitOps: why this is operable at scale**
- “ArgoCD is the reconciliation engine. Git is the source of truth; the cluster is continuously converged to match Git. This prevents drift and provides auditability and rollback-by-revert.”
- Point to the repo wiring:
   - Root GitOps entry: [bootstrap/root-app.yaml](bootstrap/root-app.yaml)
   - Backstage as a child app: [infrastructure/backstage-app.yaml](infrastructure/backstage-app.yaml)
- “Automated sync with self-heal means manual kubectl changes don’t become permanent snowflakes.”

**1:45–3:00 — AI serving: why KServe (standardization over ad-hoc services)**
- “Inference is a platform concern because it has unique scaling and operational needs. I use KServe to standardize serving APIs and runtime behavior instead of shipping custom Flask apps for every model.”
- “I define serving runtimes separately from model deployments so I can control default behavior and resource profiles.”
- Point to the artifacts:
   - Runtime: [infrastructure/kserve/sklearn-runtime.yaml](infrastructure/kserve/sklearn-runtime.yaml)
   - Example InferenceService: [apps/ai-model-alpha/inference-service.yaml](apps/ai-model-alpha/inference-service.yaml)
- “A key design choice: KServe install must be GitOps-managed so CRDs/controllers exist before deploying cluster-scoped runtimes and InferenceServices.”

**3:00–4:15 — Developer Experience: how the Golden Path removes cognitive load**
- “Backstage is the product layer. The portal isn’t the platform; it’s the UX that exposes approved workflows.”
- “The Golden Path creates a PR that adds an `apps/<name>/` folder with a compliant InferenceService manifest and required ownership metadata. Merge triggers deployment through GitOps.”
- “This prevents ‘Empty Portal syndrome’ because the portal performs real self-service actions that ship to production.”

**4:15–5:45 — Guardrails: shift-left (CI) + shift-down (admission)**
- “I enforce standards in two places:
   1) PR-time checks (shift-left): validate what will actually be deployed
   2) Admission-time policies (shift-down): prevent bypasses and enforce invariants in-cluster”
- “CI renders Helm and validates the final rendered manifests. This comes directly from my incident learnings: mis-nested Helm values can look correct in code review but fail at runtime.”
- Point to the operational proof that you treat the platform like production: [infrastructure/INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md](infrastructure/INCIDENT_BACKSTAGE_CRASHLOOP_RCA.md)
- “Kyverno policies enforce required labels (owner/costCenter), requests/limits, and safety rules like denying floating image tags.”

**5:45–6:30 — FinOps angle: preventative, not just dashboards**
- “Cost is managed by design: every workload is attributable (labels) and bounded (requests/limits). PR checks surface resource deltas early so cost changes are visible before merge.”

**6:30–7:00 — Close: why this maps to real hiring signals**
- “This matches what companies are hiring for: platforms as products (Backstage), drift control (GitOps), and guardrails baked into the platform (policy + CI).”
- “I can demonstrate both the happy path and the failure path, which is what makes it operationally credible.”
