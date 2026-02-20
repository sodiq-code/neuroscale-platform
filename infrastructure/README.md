## Infrastructure

Platform components are defined here and deployed through ArgoCD child applications under `infrastructure/apps/`.

Key folders:

- `apps/`: ArgoCD child Application manifests
- `backstage/`: Backstage Helm wrapper
- `kserve/`: runtime-level KServe resources (e.g., `ClusterServingRuntime`)
- `serving-stack/`: pinned install layer for cert-manager + Knative + Kourier + KServe
