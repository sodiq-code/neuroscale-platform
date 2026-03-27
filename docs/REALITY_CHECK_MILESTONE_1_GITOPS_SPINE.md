# Reality Check: Milestone 1 — GitOps Spine

> **This is not a tutorial where everything works.** This document records what broke, the exact terminal output, the root cause, and what it cost us operationally when building the GitOps spine of NeuroScale.

---

## What We Were Trying to Prove

Milestone A goal: ArgoCD manages platform infrastructure and application workloads from a Git repository. If someone manually deletes a resource (drift), ArgoCD detects and reverses it automatically within seconds.

The demo contract was simple:

```
delete nginx-test deployment -> ArgoCD recreates it within 20 seconds
```

Getting there was not simple.

---

## Failure 1: ArgoCD repo-server Enters Unknown Comparison State Due to Controller Dependency Ordering (40 min)

### Symptom

After setting up the root app-of-apps and pushing the first infrastructure manifests, the ArgoCD UI showed the `neuroscale-infrastructure` Application in `Unknown` status — not `Synced`, not even `OutOfSync`. Just `Unknown`.

The ArgoCD UI comparison panel showed no diff, no resource tree, nothing. The application appeared frozen.

### Terminal Output

```
$ kubectl get applications -n argocd
NAME                       SYNC STATUS   HEALTH STATUS
neuroscale-infrastructure  Unknown        Unknown
test-app                   Unknown        Unknown

$ kubectl -n argocd describe application neuroscale-infrastructure
...
Message: rpc error: code = Unavailable desc = connection refused
...
ComparedTo:
  Revision: <empty>
```

Checking the repo-server directly:

```
$ kubectl get pods -n argocd
NAME                                                READY   STATUS             RESTARTS
argocd-application-controller-0                     1/1     Running            0
argocd-repo-server-7d9f5b8c4-xqr2m                 0/1     CrashLoopBackOff   7
argocd-server-6d4b9c7f5-p8k9l                       1/1     Running            0

$ kubectl logs -n argocd argocd-repo-server-7d9f5b8c4-xqr2m --previous --tail=50
time="2026-01-13T08:22:11Z" level=fatal msg="Failed to initialize settings manager"
goroutine 1 [running]:
...
```

### Root Cause

The repo-server pod was in `CrashLoopBackOff` due to a controller dependency ordering issue during cluster bootstrap. The application controller could not reach the repo-server, so it reported all applications as `Unknown` — a valid but deeply confusing state for anyone expecting `OutOfSync` or `Error`.

**Key insight:** `Unknown` in ArgoCD does not mean "something is wrong with your manifests." It means "the comparison engine cannot run at all." These are entirely different failure modes, but the UI treats them visually similarly.

### Fix

```bash
# Force restart the repo-server
kubectl -n argocd rollout restart deploy/argocd-repo-server

# Watch until it stabilizes
kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=120s

# Then force a hard refresh on the application
kubectl -n argocd patch application neuroscale-infrastructure \
  --type merge \
  -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```

After the repo-server restarted successfully:

```
$ kubectl get applications -n argocd
NAME                       SYNC STATUS   HEALTH STATUS
neuroscale-infrastructure  OutOfSync      Healthy
test-app                   OutOfSync      Missing
```

Now we had actionable status. `OutOfSync` means "I can see Git and I can see the cluster; they differ." That is fixable.

### Business Impact

- 40 minutes lost diagnosing what appeared to be a manifest problem when it was a controller connectivity problem.
- The GitOps self-heal demo contract cannot be validated until the repo-server is healthy. If this had been a production cluster, all ArgoCD-managed services would have stopped receiving drift corrections during the outage.

### Prevention

Added to operational runbook: always check repo-server health before diagnosing sync errors.

```bash
# Quick repo-server health check
kubectl -n argocd get pods | grep repo-server
kubectl -n argocd logs deploy/argocd-repo-server --tail=20
```

---

## Failure 2: ArgoCD test-app Stuck in Progressing — Stale ingress-nginx Admission Webhook Blocks All Resource Creation

### Symptom

After fixing the repo-server, the root app synced but the `test-app` child Application stayed in `Progressing` for over 5 minutes. No deployment appeared in the `default` namespace.

```
$ kubectl get applications -n argocd
NAME                       SYNC STATUS   HEALTH STATUS
neuroscale-infrastructure  Synced         Healthy
test-app                   Synced         Progressing   <-- stuck here

$ kubectl get deploy -n default
No resources found in default namespace.
```

The ArgoCD UI showed the Deployment resource as "missing" in the resource tree but "synced" in status — a contradiction.

### Terminal Output (from ArgoCD application resource detail)

```
$ kubectl -n argocd get application test-app -o yaml | grep -A 20 conditions
  conditions:
  - lastTransitionTime: "2026-01-13T09:15:42Z"
    message: 'Failed sync attempt to <revision>: one or more objects failed to apply,
      reason: Internal error occurred: failed calling webhook "validate.nginx.ingress.kubernetes.io":
      failed to call webhook: Post "https://ingress-nginx-controller-admission.ingress-nginx.svc:443/networking/v1/ingresses?timeout=10s":
      dial tcp 10.96.x.x:443: connect: connection refused'
    type: SyncError
```

### Root Cause

An unrelated ingress validation webhook from a previous cluster experiment was still registered but pointing to a service that no longer existed. Kubernetes admission webhooks are cluster-scoped; a webhook for `ingress-nginx` that was never cleaned up was intercepting all resource creation attempts and failing them because the webhook backend was gone.

This had nothing to do with ArgoCD or our manifests. The `nginx-test` Deployment was being blocked by a dead webhook.

### Fix

```bash
# List all validating webhooks
kubectl get validatingwebhookconfigurations

# Delete the stale one
kubectl delete validatingwebhookconfiguration ingress-nginx-admission

# Force ArgoCD to retry sync
kubectl -n argocd patch application test-app \
  --type merge \
  -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```

After deletion:

```
$ kubectl get applications -n argocd
NAME                       SYNC STATUS   HEALTH STATUS
neuroscale-infrastructure  Synced         Healthy
test-app                   Synced         Healthy

$ kubectl get deploy -n default
NAME          READY   UP-TO-DATE   AVAILABLE   AGE
nginx-test    1/1     1            1           23s
```

### Business Impact

A stale webhook from a previous workload silently blocked all resource creation in the default namespace. In a shared cluster, this class of failure can silently prevent unrelated teams' deployments for hours without any obvious error message — the admission error only appears in the ArgoCD events log, not on the deployment itself.

---

## Failure 3: Self-Heal Demo Pod Stuck in Pending — CPU Requests Exceed Available k3d Node Capacity (45 sec)

### Symptom

The drift self-heal demo — delete `nginx-test`, watch it come back — worked, but the recreated pod spent 45 seconds in `Pending` before becoming `Running`. This was enough time to confuse the demo into looking like it had failed.

```
$ kubectl delete deploy nginx-test -n default
deployment.apps "nginx-test" deleted

# ... 20 seconds later ...
$ kubectl get deploy nginx-test -n default
Error from server (NotFound): deployments.apps "nginx-test" not found

# ... 35 seconds later (after ArgoCD sync cycle) ...
$ kubectl get deploy nginx-test -n default
NAME          READY   UP-TO-DATE   AVAILABLE   AGE
nginx-test    0/1     1            0           8s

$ kubectl get pods -n default
NAME                         READY   STATUS    RESTARTS   AGE
nginx-test-7d9f5b8c4-xqr2m  0/1     Pending   0          12s
```

Checking why the pod was pending:

```
$ kubectl describe pod nginx-test-7d9f5b8c4-xqr2m -n default
Events:
  Warning  FailedScheduling  15s   default-scheduler  
    0/1 nodes are available: 1 Insufficient cpu. 
    preemption: 0/1 nodes are available: 1 No preemption victims found for incoming pod.
```

### Root Cause

The test Deployment had CPU requests set to `500m` (half a core). During the demo, other platform components (ArgoCD application controller, Backstage) were consuming available CPU on the single k3d node. The scheduler could not place the pod immediately.

### Fix

Reduced `nginx-test` resource requests to match actual usage:

```yaml
# apps/test-app/deployment.yaml
resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 200m
    memory: 128Mi
```

After this change, the self-heal demo completes within 15 seconds consistently.

### Business Impact

The self-heal demo is the primary Milestone A proof point. A 45-second pending state that looks like failure undermines the entire GitOps narrative during an interview or demo session. Resource sizing on a constrained local cluster is a real concern, not just a "production" problem.

---

## What Milestone 1 Actually Proves (After the Failures)

After working through the above failures, the GitOps spine worked reliably:

```
$ kubectl delete deploy nginx-test -n default
deployment.apps "nginx-test" deleted

$ sleep 20 && kubectl get deploy nginx-test -n default
NAME          READY   UP-TO-DATE   AVAILABLE   AGE
nginx-test    1/1     1            1           15s
```

**Interview-ready framing:** "GitOps doesn't mean zero failure. It means failure is deterministic and recoverable through Git operations. Week 1 proved that by debugging three distinct failure modes before the self-heal demo was reliable."

---

## Debugging Commands Reference: ArgoCD Comparison Failures, Stale Webhooks, and Pod Scheduling

```bash
# Diagnose ArgoCD comparison failures
kubectl -n argocd get pods
kubectl -n argocd logs deploy/argocd-repo-server --tail=30
kubectl -n argocd logs deploy/argocd-application-controller --tail=30

# Check application sync status and events
kubectl -n argocd describe application <app-name>
kubectl -n argocd get application <app-name> -o yaml | grep -A 20 conditions

# Discover stale admission webhooks
kubectl get validatingwebhookconfigurations
kubectl get mutatingwebhookconfigurations

# Force full ArgoCD re-sync
kubectl -n argocd patch application <app-name> \
  --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```

---

## See Also

- `docs/WEEK_1_LEARNING_REVIEW.md` — milestone close-out with design decisions
- `bootstrap/root-app.yaml` — root app-of-apps with selfHeal and prune settings
- `apps/test-app/deployment.yaml` — the workload used in the self-heal demo
