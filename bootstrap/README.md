## Bootstrap

`root-app.yaml` is the GitOps entrypoint that seeds ArgoCD app-of-apps.

- Root app manifest: `bootstrap/root-app.yaml`
- Current source path: `infrastructure/apps`

Apply command:

```bash
kubectl apply -f bootstrap/root-app.yaml
```
