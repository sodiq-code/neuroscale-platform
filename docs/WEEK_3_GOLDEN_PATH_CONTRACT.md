# Week 3 — Backstage Golden Path Contract

This document defines the minimal, deterministic “Golden Path” for NeuroScale.

## Goal
From Backstage, a developer can create a PR that adds a new KServe model endpoint. When the PR is merged, ArgoCD deploys it automatically.

## Contract (Inputs → Outputs)
### Inputs (Backstage form)
Template: `KServe model endpoint`
- `name` (required): lowercase DNS label (e.g. `my-model`)
- `modelFormat` (default: `sklearn`)
- `storageUri` (default: `gs://kfserving-examples/models/sklearn/1.0/model`)

### Outputs (GitOps artifacts)
The template creates a PR against `main` in `sodiq-code/neuroscale-platform` that adds exactly:
- `apps/<name>/inference-service.yaml`
  - KServe `InferenceService` named `<name>` in namespace `default`
- `infrastructure/apps/<name>-app.yaml`
  - ArgoCD `Application` named `<name>` that points at `apps/<name>`

### Merge behavior
After merge:
- ArgoCD app-of-apps discovers the new child app YAML under `infrastructure/apps/`.
- ArgoCD sync creates/updates the KServe `InferenceService`.
- The endpoint becomes Ready through the existing KServe/Knative/Kourier stack.

## Security model
- No secrets are committed to Git.
- Backstage reads `GITHUB_TOKEN` from a Kubernetes Secret (`neuroscale-backstage-secrets`) via an env var.
- The Helm values configure GitHub integration as `integrations.github[*].token: ${GITHUB_TOKEN}`.

## Preconditions
- Backstage is deployed by ArgoCD (child app `neuroscale-backstage`).
- KServe stack is installed and healthy.
- A GitHub token exists with permissions to open PRs against the repo.

## Verification checklist (DoD)
1. Backstage is reachable (port-forward is OK).
2. `/create/actions` includes `publish:github:pull-request`.
3. Running the template creates a PR with the two expected files.
4. Merging the PR causes ArgoCD to create a new `Application`.
5. The new `InferenceService` becomes `Ready`.

### Verification commands (cluster)
Create the GitHub token Secret (safe even before token exists; Backstage reads it as optional until you set it):

```sh
kubectl create ns backstage >/dev/null 2>&1 || true
kubectl -n backstage create secret generic neuroscale-backstage-secrets \
  --from-literal=GITHUB_TOKEN=YOUR_TOKEN
```

Check Backstage is running:

```sh
kubectl -n backstage get deploy,pods,svc
```

Port-forward and verify action registration:

```sh
kubectl -n backstage port-forward deploy/neuroscale-backstage 7007:7007
```

Then open:
- `http://localhost:7007/create/actions`
- `http://localhost:7007/create`

After merging the generated PR, verify ArgoCD created the new child app and KServe got the new service:

```sh
kubectl -n argocd get applications.argoproj.io
kubectl -n default get inferenceservices.serving.kserve.io
```

## Defense drill (you should be able to explain)
- Why we generate an ArgoCD child `Application` per endpoint (and what tradeoffs it has).
- How Backstage’s template becomes a Catalog entity (what `catalog.locations` does).
- Why we avoid `envFrom.secretRef` for GitHub token wiring (and how `optional: true` changes failure modes).
- How a merge turns into a running endpoint (Backstage → PR → GitOps → Argo sync → KServe controllers).
