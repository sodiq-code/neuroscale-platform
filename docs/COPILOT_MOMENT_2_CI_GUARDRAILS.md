# Copilot Moment 2: CI Guardrails — Making Unsafe Workloads Impossible to Merge

## The Problem

Kyverno was enforcing policies at admission time (cluster-side), but non-compliant manifests could still be merged into Git. Since ArgoCD auto-syncs from Git, a merged bad manifest would enter a failed sync loop — the policy worked, but the developer experience was terrible. You'd merge, wait, and then discover your manifest was denied.

We needed shift-left enforcement: catch policy violations *at PR time*, before merge.

## Where Copilot Helped

**The question I asked Copilot:**

> "I have 5 Kyverno ClusterPolicies in infrastructure/kyverno/policies/. I need a GitHub Actions workflow that validates all manifests under apps/ against these policies before merge. The catch: kyverno-cli apply sometimes exits 0 even when violations exist. How do I build a CI check that's impossible to false-green?"

**What Copilot helped me build:**

1. **Schema validation first** (kubeconform) — catches malformed YAML before policy checks even run.

2. **Per-file resource flags** — `kyverno-cli` requires a separate `--resource` flag per file. Passing all paths after a single flag silently ignores every path after the first. Copilot identified this undocumented behavior and generated the `mapfile`-based loop:

```bash
resource_args=()
for f in "${app_files[@]}"; do
  resource_args+=(--resource "$f")
done
```

3. **Dual exit-code + stdout check** — guards against the false-green where kyverno-cli exits 0 despite violations:

```bash
if [ "${kyverno_exit}" -ne 0 ] \
    || grep -qE "^FAIL" /tmp/kyverno-output.txt \
    || grep -qE "fail: [1-9][0-9]*" /tmp/kyverno-output.txt; then
  echo "Kyverno policy violations detected. Failing CI."
  exit 1
fi
```

4. **Resource cost proxy** — a Python script that parses CPU/memory requests from changed manifests and posts a cost delta as a PR comment.

## The Result

The CI pipeline now runs three enforcement layers:

| Check | Tool | What It Catches |
|-------|------|----------------|
| Schema validation | kubeconform | Malformed YAML, wrong API versions |
| Policy simulation | kyverno-cli | Missing labels, no resource limits, :latest tags, root containers |
| Resource delta | Python + PyYAML | CPU/memory cost impact of the change |

A non-compliant manifest now gets this at PR time:

```
Kyverno policy violations detected. Failing CI.
FAIL - require-standard-labels-inferenceservice
  check-owner-and-cost-center-on-isvc: InferenceService resources must set
  metadata.labels.owner and metadata.labels.cost-center
```

**Unsafe workloads became impossible to merge.**

## Why This Shows Judgment, Not Just Code Generation

The hard part was not writing a CI workflow — it was making a CI workflow that's *impossible to circumvent*:

- The false-green bug (kyverno-cli exiting 0 on violations) would have made the entire guardrail theater. Copilot helped identify and patch it.
- The per-file `--resource` flag issue is an undocumented kyverno-cli behavior that most CI implementations get wrong.
- The resource delta comment gives reviewers cost context without requiring any manual calculation.

This is platform safety engineering, not script writing.
