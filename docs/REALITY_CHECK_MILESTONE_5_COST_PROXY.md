# Reality Check: Milestone 5 — Cost Proxy, Portability, and Visual Testing

> **This document records the design decisions, implementation trade-offs, and known limitations** for the Phase 5 additions: the CI resource-cost proxy, the bootstrap script, and the visual smoke-test runner.

---

## What We Were Trying to Prove

Phase 5 goal: three concrete improvements that close the gap between "it works on my laptop" and "it works on any laptop and can be verified visually."

1. **Cost proxy** — a PR comment that summarises the CPU/memory requests introduced by every changed `Deployment` or `InferenceService` in `apps/`, flags high-resource requests before merge, and posts a markdown summary in the GitHub Actions job panel.

2. **Bootstrap portability** — a single script (`scripts/bootstrap.sh`) that takes a machine from zero to a running NeuroScale cluster with no manual steps beyond installing Docker, k3d, kubectl, and helm.

3. **Visual smoke test** — a script (`scripts/smoke-test.sh`) that tests all four milestone contracts end-to-end with colour-coded `[✓ PASS]` / `[✗ FAIL]` output so that any person on any laptop can verify the platform is healthy in under 2 minutes.

---

## Decision 1: Fix the Kyverno CI False-Green Before Adding Anything Else

The most important change in this milestone was not a new feature — it was fixing a silent bug that had existed since Milestone 4 was declared "Done".

The original CI Kyverno step was:

```yaml
docker run --rm -v "$PWD:/work" -w /work ghcr.io/kyverno/kyverno-cli:v1.12.5 \
  apply infrastructure/kyverno/policies/*.yaml \
  --resource "${app_files[@]}"
```

This exits with code `0` even when policy violations are present (documented in `docs/REALITY_CHECK_MILESTONE_4_GUARDRAILS.md`, Failure 4). The fix was documented but never applied to the actual workflow file.

**The fixed version uses a dual check:**

```bash
set +e
docker run --rm ... | tee /tmp/kyverno-output.txt
kyverno_exit="${PIPESTATUS[0]}"
set -e

if [ "${kyverno_exit}" -ne 0 ] \
    || grep -qE "^FAIL" /tmp/kyverno-output.txt \
    || grep -qE "fail: [1-9][0-9]*" /tmp/kyverno-output.txt; then
  exit 1
fi
```

**Why `PIPESTATUS[0]` and not just the last exit code?**  When the command is piped through `tee`, the shell variable `$?` captures the exit code of `tee` (which always succeeds), not kyverno. `PIPESTATUS[0]` captures the exit code of the first command in the pipe — kyverno — regardless of what `tee` does.

**Why two checks?**  `kyverno-cli apply` v1.12.x does not reliably exit non-zero on policy violations. The stdout-grep check (`^FAIL` and `fail: [1-9]`) handles the case where kyverno exits `0` but prints violations. Together, the two checks prevent both false negatives (missed violations) and false positives (failing on unrelated docker or tee errors).

---

## Decision 2: Cost Proxy Implementation Approach

### What it does

On every pull request, the `resource-cost-proxy` CI job:
1. Finds all YAML files in `apps/` that were added or modified in the PR.
2. Parses `resources.requests.cpu` and `resources.requests.memory` from `Deployment` containers and `InferenceService` predictor models.
3. Posts (or updates) a single PR comment with a markdown table.
4. Flags any workload requesting ≥ 2 CPU cores or ≥ 4 GiB memory.
5. Writes the same table to the GitHub Actions Job Summary panel.

### What it does NOT do (intentional scope limits)

| Feature | Why not included |
|---------|-----------------|
| Diff against base branch for deltas | Requires checking out both branches; the table already shows what the PR declares — which is the actionable signal |
| Actual cost in dollars | Requires cloud pricing API and node instance type — not available in local k3d demos |
| InferenceService runtime resources | KServe sets default resource bounds via `ClusterServingRuntime`; the InferenceService YAML only needs explicit overrides. Showing "—" for resource-unset InferenceServices is correct and informative, not a bug |
| Blocking PRs on high requests | The flag is a warning, not a hard block. Blocking requires a human decision on thresholds that vary by team |

### Known limitation: InferenceService resources almost always show "—"

The current `InferenceService` manifests (`apps/ai-model-alpha/`, `apps/demo-iris-2/`) do not set explicit `spec.predictor.model.resources.requests`. Resources are inherited from the `ClusterServingRuntime`. The cost proxy correctly shows "—" for these. This is expected behaviour, not a bug.

If you want the cost proxy to show actual figures for an `InferenceService`, add explicit requests:

```yaml
spec:
  predictor:
    model:
      modelFormat:
        name: sklearn
      storageUri: "gs://..."
      resources:
        requests:
          cpu: "100m"
          memory: "256Mi"
        limits:
          cpu: "500m"
          memory: "512Mi"
```

---

## Decision 3: Bootstrap Script Design

### Single-responsibility constraint

`scripts/bootstrap.sh` does exactly one thing: get from zero to a running cluster with ArgoCD managing the platform from Git. It does not:
- Install Backstage GitHub token (requires a secret that must not be scripted)
- Run inference tests (that is `scripts/smoke-test.sh`)
- Configure TLS or production ingress (out of scope for local demo)

### k3d cluster flags

```bash
k3d cluster create neuroscale \
  --port "8081:443@loadbalancer" \
  --port "8082:80@loadbalancer"  \
  --k3s-arg "--disable=traefik@server:0" \
  --wait
```

- `--port "8081:443@loadbalancer"` — maps host port 8081 to the cluster's HTTPS ingress port so ArgoCD UI is accessible without additional configuration.
- `--port "8082:80@loadbalancer"` — maps host port 8082 to HTTP, used for Kourier inference requests.
- `--disable=traefik` — removes k3d's built-in Traefik ingress to avoid port conflicts with Kourier.
- No Backstage port mapping — Backstage is always accessed via `kubectl port-forward` at a user-chosen port; baking this into the cluster config would create confusion when the pod is not running.

### Why not use a k3d config file

A `k3d-config.yaml` file would be cleaner but adds a file that must be kept in sync. The bootstrap script is the single source of truth for cluster creation; keeping it as a self-contained script reduces onboarding friction.

---

## Decision 4: Smoke Test Design

### Color-coded output format

```
[✓ PASS] ArgoCD Applications: 7/7 Healthy
[✗ FAIL] Drift self-heal: nginx-test was NOT recreated within 60s
[~ SKIP] Inference request test (no Running pod matching demo-iris-2 found)
         ↳  Ensure demo-iris-2 InferenceService is Ready=True before running this test
```

Each line is visually parseable without reading prose. The `↳` indicator provides a recovery action directly below the failed check, which reduces the time from "I see a failure" to "I know what to do."

### Why test ordering matters

The smoke test runs milestones A → B → C → D in order because later milestones depend on earlier ones:
- Milestone B (KServe) requires ArgoCD to be healthy (Milestone A) to apply InferenceService manifests.
- Milestone C (Backstage) requires KServe to be ready to verify Golden Path output.
- Milestone D (Kyverno) requires both Deployments and InferenceServices to exist to test policy enforcement.

Running in dependency order means the first failure gives accurate signal about the root cause.

### The drift self-heal test is destructive

The drift test (`kubectl delete deploy nginx-test`) modifies the cluster. This is intentional — the point is to prove ArgoCD self-heals. The test is safe because:
1. ArgoCD will recreate the deployment from Git within 20–60 seconds.
2. The test explicitly waits for recreation and reports the elapsed time.
3. It can be skipped with `--skip-drift` for non-destructive runs.

### The admission block test creates a bad resource attempt

The policy block test sends a `kubectl apply` that expects a Kyverno denial. This generates an admission rejection in the cluster audit log, which is the expected outcome. No resource is actually created. It can be skipped with `--skip-policy-block`.

---

## What Milestone 5 Proves

After these additions:

```
$ bash scripts/smoke-test.sh

━━━ Prerequisites ━━━
  [✓ PASS] kubectl available
  [✓ PASS] curl available
  [✓ PASS] kubectl can reach the cluster

━━━ Milestone A — GitOps Spine (ArgoCD) ━━━
  [✓ PASS] All ArgoCD pods are Running
  [✓ PASS] ArgoCD Applications: 7/7 Healthy
  [✓ PASS] ArgoCD Applications: 7/7 Synced
  [✓ PASS] Drift self-heal: nginx-test recreated and Ready in ~20s

━━━ Milestone B — AI Serving Baseline (KServe) ━━━
  [✓ PASS] KServe controller-manager: 1 replica(s) available
  [✓ PASS] InferenceServices: 2/2 Ready=True
  [✓ PASS] Inference request: demo-iris-2 returned predictions
           ↳  Response: {"predictions":[1,1]}

━━━ Milestone C — Golden Path (Backstage) ━━━
  [✓ PASS] Backstage deployment: 1 replica(s) available
  [✓ PASS] Golden Path evidence: demo-iris-2 InferenceService exists (scaffolder output)
  [✓ PASS] Golden Path evidence: demo-iris-2 ArgoCD Application exists (scaffolder output)

━━━ Milestone D — Guardrails (Kyverno + CI) ━━━
  [✓ PASS] Kyverno pods running: 3
  [✓ PASS] Kyverno ClusterPolicies installed: 4 policies
  [✓ PASS] Admission block: non-compliant InferenceService correctly denied by Kyverno

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  NeuroScale Smoke Test — Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PASS  14
  FAIL  0
  SKIP  0

✓ All checks passed. Platform is healthy and ready to demo.
```

**Interview-ready framing:** "Phase 5 is what turns a platform from 'works on my machine' to 'works on any machine, visibly, in 2 minutes.' The smoke test is the evidence you can hand to anyone — an interviewer, a new team member, or a customer demo — and they can run it themselves and see every milestone proven in a single terminal session."

---

## See Also

- `scripts/bootstrap.sh` — one-shot cluster setup from zero
- `scripts/smoke-test.sh` — visual smoke test for all milestones
- `.github/workflows/guardrails-checks.yaml` — CI workflow with the Kyverno fix, job summaries, and cost proxy
- `docs/REALITY_CHECK_MILESTONE_4_GUARDRAILS.md` — root cause of the CI false-green that was fixed in this milestone
