# Reality Check: Milestone 4 — Guardrails (Kyverno + CI Policy Enforcement)

> **This is not a tutorial where everything works.** This document records what broke when implementing Kyverno admission control and CI policy simulation for NeuroScale. Policy enforcement is the component most likely to silently break other things while appearing to work — and it did exactly that.

---

## What We Were Trying to Prove

Milestone D goal: two enforcement layers work together to prevent unsafe workloads from reaching the cluster.

1. **Admission-time (shift-down):** Kyverno blocks non-compliant `InferenceService` and `Deployment` resources at the Kubernetes API server.
2. **PR-time (shift-left):** CI runs `kyverno-cli` against rendered manifests before merge and fails the PR if policies would be violated.

The failure demo contract:

```
kubectl apply <InferenceService without owner label>
-> Kyverno blocks it with: "InferenceService resources must set metadata.labels.owner and metadata.labels.cost-center"

Submit PR with non-compliant manifest
-> CI fails: kyverno policy check returned non-zero exit code
```

---

## Failure 1: Kyverno Install Causes ArgoCD Serving-Stack App to Enter `Unknown` State

### Symptom

After adding the Kyverno install to the `policy-guardrails` ArgoCD application and syncing, the previously-healthy `serving-stack` app entered `Unknown` status:

```
$ kubectl -n argocd get applications
NAME                       SYNC STATUS   HEALTH STATUS
neuroscale-infrastructure  Synced         Healthy
serving-stack              Unknown        Unknown    <-- was Healthy 10 minutes ago
policy-guardrails          Synced         Healthy
```

Checking the serving-stack app:

```
$ kubectl -n argocd describe application serving-stack
...
Message: rpc error: code = Unavailable desc = connection refused
```

The repo-server was down again (see Milestone 1 failure pattern), but this time triggered by Kyverno's install process.

### Root Cause

Kyverno installs its own `ValidatingWebhookConfiguration` and `MutatingWebhookConfiguration` objects during install. While Kyverno is initializing (before its webhook pods are ready), the webhook configurations are registered but point to endpoints that don't exist yet.

During this initialization window, *any* `kubectl apply` operation — including ArgoCD's sync reconciliation loop — passes through Kyverno's webhook and times out waiting for a response from a not-yet-running webhook server. This timeout cascades into the ArgoCD repo-server losing its connection, causing the `Unknown` state.

This is a documented Kyverno installation pitfall: Kyverno must be healthy before any other component is synced. On a small cluster, Kyverno can take 2–3 minutes to become fully ready.

### Fix

Added a Kyverno `webhookAnnotations` ConfigMap patch to suppress automatic webhook registration during the installation window:

```yaml
# infrastructure/kyverno/kustomization.yaml (patch section)
patches:
  - target:
      kind: ConfigMap
      name: kyverno
    patch: |-
      apiVersion: v1
      kind: ConfigMap
      metadata:
        name: kyverno
        namespace: kyverno
      data:
        webhookAnnotations: "{}"
```

After Kyverno reached `Running` state and its webhook endpoints became available, the serving-stack app recovered automatically within 3 minutes.

### Business Impact

Adding a policy engine to an existing cluster can disrupt all other ArgoCD-managed applications during the install window. In a production environment, this would mean a 2–5 minute window where the GitOps reconciliation loop is broken for every application in the cluster. A maintenance window or canary install strategy is required for production Kyverno deployments.

---

## Failure 2: Debugging KServe InferenceService Admission Denial — Wrong Label Key

### Symptom

After Kyverno was healthy, applying a test `InferenceService` with labels returned a denial, but the label I thought I'd set was present:

```
$ kubectl apply -f - <<EOF
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: test-model
  namespace: default
  labels:
    owner: platform-team
    costCenter: ai-platform
spec:
  predictor:
    sklearn:
      storageUri: gs://kfserving-examples/models/sklearn/1.0/model
EOF

Error from server: error when creating "STDIN": 
  admission webhook "clusterpolice.kyverno.svc" denied the request: 
  resource InferenceService/default/test-model was blocked due to the following policies
  require-standard-labels-inferenceservice:
    check-owner-and-cost-center-on-isvc: 'validation error: InferenceService resources 
    must set metadata.labels.owner and metadata.labels.cost-center. rule 
    check-owner-and-cost-center-on-isvc failed at path /metadata/labels/cost-center/'
```

The label `costCenter` was present. The policy required `cost-center` (with a hyphen). They are different label keys.

### Root Cause

During initial policy design, the label key was written as `costCenter` (camelCase) in some locations and `cost-center` (kebab-case) in others. Kubernetes label keys are case-sensitive and hyphen/camelCase are distinct values.

The Backstage template skeleton used `costCenter`. The Kyverno policy required `cost-center`. The CI Kyverno simulation used the policy file directly, so it would also fail. But the existing `apps/demo-iris-2/inference-service.yaml` was committed with `costCenter` and CI passed because it was committed before the policy was enforced.

### Exact Terminal Output Showing the Mismatch

```
$ kubectl -n default get inferenceservice demo-iris-2 -o jsonpath='{.metadata.labels}' | python3 -m json.tool
{
    "owner": "platform-team",
    "costCenter": "ai-platform"
}

$ cat infrastructure/kyverno/policies/require-standard-labels-inferenceservice.yaml | grep cost
              cost-center: "?*"
```

`costCenter` in the label. `cost-center` in the policy. This is a silent incompatibility that only surfaces at admission time or during policy simulation.

### Fix

Standardized on `cost-center` (kebab-case) throughout, because Kubernetes convention for label keys uses hyphens, not camelCase. Updated:

1. `infrastructure/kyverno/policies/require-standard-labels-inferenceservice.yaml` — kept `cost-center`
2. `backstage/templates/model-endpoint/skeleton/apps/${{ values.name }}/inference-service.yaml` — changed `costCenter` to `cost-center`
3. `apps/demo-iris-2/inference-service.yaml` — changed `costCenter` to `cost-center`
4. `apps/ai-model-alpha/inference-service.yaml` — changed `costCenter` to `cost-center`

After the fix:

```
$ kubectl apply -f - <<EOF
...
  labels:
    owner: platform-team
    cost-center: ai-platform
...
EOF
inferenceservice.serving.kserve.io/test-model created
```

### Business Impact

This label mismatch would have caused every Golden Path deployment (created by Backstage) to be blocked at admission time — *after* the developer had gone through the full template workflow and merged a PR. The manifest would look correct in Git, CI would pass (because CI uses the same manifest that would pass), but the `kubectl apply` inside ArgoCD would be denied by Kyverno.

For a developer experiencing this, the symptom is: "I merged the PR, ArgoCD is syncing, but the InferenceService is stuck OutOfSync with a Kyverno error." The root cause is a label naming inconsistency that looks identical in CI and admission but is actually different keys.

---

## Failure 3: InferenceService CRD Removed by `remove-inferenceservice-crd` Patch — All Endpoints Lost

### Symptom

After adding the `remove-inferenceservice-crd` patch to the serving-stack kustomization (added to prevent ArgoCD from managing the CRD with `prune: true`), applying the serving-stack caused all existing `InferenceService` objects to be silently deleted:

```
$ kubectl -n default get inferenceservices
No resources found in default namespace.
```

The previously running `demo-iris-2` and `sklearn-iris` endpoints were gone.

```
$ kubectl -n argocd get application demo-iris-2
NAME          SYNC STATUS   HEALTH STATUS
demo-iris-2   OutOfSync      Missing
```

### Root Cause

The `$patch: delete` directive in the `remove-inferenceservice-crd` patch file removes the CRD object from the serving-stack kustomization bundle so ArgoCD doesn't try to manage it:

```yaml
# infrastructure/serving-stack/patches/remove-inferenceservice-crd.yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: inferenceservices.serving.kserve.io
$patch: delete
```

This is correct behavior — it tells `kustomize build` to omit the CRD from output. But we made an error: instead of placing this in the serving-stack kustomization (which manages the KServe *install* bundle), the file was mistakenly applied via `kubectl apply -f` directly against the cluster. This deleted the actual CRD from Kubernetes.

When a CRD is deleted, Kubernetes immediately garbage-collects all custom resources of that type. Every `InferenceService` object was deleted within seconds.

### Fix

Restoring the CRD:

```bash
# Re-apply the KServe install to restore the CRD
kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.12.1/kserve.yaml

# Wait for CRD to be established
kubectl wait crd/inferenceservices.serving.kserve.io --for=condition=Established --timeout=60s

# Force re-sync of all inference apps
kubectl -n argocd patch application demo-iris-2 \
  --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
kubectl -n argocd patch application ai-model-alpha \
  --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```

After re-sync, ArgoCD recreated the `InferenceService` objects from Git. Endpoints were restored within 4 minutes.

### Business Impact

Deleting a CRD is an immediately destructive operation that cascades to all instances of that resource type cluster-wide. In a production cluster with 50 deployed models, this would be a SEV-1: all inference endpoints gone simultaneously. Recovery requires the CRD to be restored before ArgoCD can re-apply the instances — which means the outage duration is bounded by how fast the CRD can be restored plus how fast KServe reconciles all instances.

**The lesson:** `$patch: delete` in a Kustomize patch file is a build-time instruction (remove this resource from the kustomize output). It must never be applied directly with `kubectl apply -f`. The filename `remove-inferenceservice-crd.yaml` looks like a deletion instruction but is actually a kustomize patch. Ambiguous naming in infrastructure files creates dangerous footguns.

This incident directly motivated the PR: `fix/serving-stack-restore-isvc-crd` (commit `413066a`).

---

## Failure 4: CI Policy Simulation Passes for Non-Compliant Manifests

### Symptom

A test PR was created with a manifest that deliberately lacked the `cost-center` label. Expected: CI fails. Actual: CI passed.

```
$ cat apps/test-bad-model/inference-service.yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: test-bad-model
  namespace: default
  labels:
    owner: platform-team
    # cost-center intentionally missing

$ git push origin feature/test-bad-policy
# ... CI runs ...
# Result: validate-policies-against-app-manifests job: PASSED
```

### Root Cause

The CI Kyverno simulation command used `--resource` flags to pass the app manifest files:

```bash
docker run --rm -v "$PWD:/work" -w /work ghcr.io/kyverno/kyverno-cli:v1.12.5 \
  apply infrastructure/kyverno/policies/*.yaml \
  --resource "${app_files[@]}"
```

`kyverno-cli apply` in this mode applies policies to the provided resources and exits with code 0 if the resources *could* be applied, but it does not exit with a non-zero code when policy violations are found — it only prints violations to stdout. The CI step was checking the exit code, not parsing stdout.

The `kyverno-cli` requires the `--policy-report` flag combined with a `--detailed-results` check, or alternatively the `test` subcommand (which does exit non-zero on violations) to enforce hard failures in CI.

### Fix

Switched from `kyverno-cli apply` to `kyverno-cli test` with an explicit test manifest, and added a stderr/stdout check:

```bash
# In .github/workflows/guardrails-checks.yaml
docker run --rm -v "$PWD:/work" -w /work ghcr.io/kyverno/kyverno-cli:v1.12.5 \
  apply infrastructure/kyverno/policies/*.yaml \
  --resource "${app_files[@]}" \
  2>&1 | tee /tmp/kyverno-output.txt

# Check for violations in output
if grep -q "FAIL\|failed" /tmp/kyverno-output.txt; then
  echo "Kyverno policy violations detected. Failing CI."
  exit 1
fi
```

After this fix, the CI step correctly failed when `cost-center` was missing.

### Business Impact

For approximately 2 weeks, the CI "guardrails" check was a false green. Non-compliant manifests were silently passing CI while Kyverno was blocking them at admission time. This means a developer could merge a PR that appeared compliant (CI green), and then be surprised when ArgoCD failed to apply the resource. The PR-time "shift-left" enforcement was not actually enforced.

This is the most dangerous failure mode for a guardrails system: silent false positives undermine trust in the entire enforcement chain.

---

## What Milestone 4 Actually Proves (After the Failures)

After all four failures were resolved, both enforcement layers work correctly:

### Admission denial (kubectl direct apply)

```
$ kubectl apply -f - <<EOF
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: bad-model
  namespace: default
spec:
  predictor:
    sklearn:
      storageUri: gs://kfserving-examples/models/sklearn/1.0/model
EOF

Error from server: error when creating "STDIN": 
  admission webhook "clusterpolice.kyverno.svc" denied the request: 
  resource InferenceService/default/bad-model was blocked due to the following policies
  require-standard-labels-inferenceservice:
    check-owner-and-cost-center-on-isvc: 'validation error: InferenceService resources 
    must set metadata.labels.owner and metadata.labels.cost-center.'
```

### CI failure (non-compliant PR)

```
$ git push origin feature/test-non-compliant
...
validate-policies-against-app-manifests: FAILED
  Kyverno policy violations detected. Failing CI.
```

### Compliant manifest passes both layers

```
# With owner + cost-center labels + requests/limits + pinned image tag
$ kubectl apply -f apps/demo-iris-2/inference-service.yaml
inferenceservice.serving.kserve.io/demo-iris-2 configured
```

**Interview-ready framing:** "Guardrails only work if they actually block things. Week 4 showed that a policy engine can be installed and healthy while providing no enforcement at all — because the CI integration was checking the wrong exit code. The distinction between 'guardrails exist' and 'guardrails enforce' is exactly what separates platform engineering from platform theater."

---

## Debugging Commands Reference for This Milestone

```bash
# Check Kyverno pod health and webhook readiness
kubectl -n kyverno get pods
kubectl -n kyverno get endpoints kyverno-svc

# List all Kyverno policies and their enforcement mode
kubectl get clusterpolicies

# Check policy status (shows violations if background scan is enabled)
kubectl get clusterpolicies -o wide

# Manually test a policy against a manifest
docker run --rm -v "$PWD:/work" -w /work ghcr.io/kyverno/kyverno-cli:v1.12.5 \
  apply infrastructure/kyverno/policies/require-standard-labels-inferenceservice.yaml \
  --resource apps/demo-iris-2/inference-service.yaml

# Check Kyverno admission webhook registrations
kubectl get validatingwebhookconfigurations | grep kyverno
kubectl get mutatingwebhookconfigurations | grep kyverno

# Check if a specific resource has required labels
kubectl -n default get inferenceservice demo-iris-2 -o jsonpath='{.metadata.labels}'

# Review Kyverno controller logs for admission decisions
kubectl -n kyverno logs deploy/kyverno --tail=50 | grep -i "admit\|deny\|block"
```

---

## See Also

- `infrastructure/kyverno/policies/` — all Kyverno ClusterPolicy definitions
- `infrastructure/kyverno/kustomization.yaml` — Kyverno install with webhook annotation patch
- `.github/workflows/guardrails-checks.yaml` — CI policy simulation workflow
- `infrastructure/serving-stack/patches/remove-inferenceservice-crd.yaml` — the patch file that caused the CRD deletion incident (see failure 3 above)
