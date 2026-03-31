# Reality Check: Milestone 2 — KServe AI Serving Baseline

> **This is not a tutorial where everything works.** This document records what broke when installing KServe on a local k3d cluster and getting one inference endpoint to respond. The happy path takes 10 minutes. The real path took two days.

---

## What We Were Trying to Prove

Milestone B goal: a single `InferenceService` named `sklearn-iris` reaches `Ready=True` and responds to a prediction request with a valid JSON payload. The install must be GitOps-managed (not "I ran some scripts").

---

## Failure 1: KServe InferenceService Stuck Not Ready — Istio vs Kourier Ingress Mismatch Causes ReconcileError Loop (3 hours)

### Symptom

After applying the KServe installation via ArgoCD (serving-stack app), the `InferenceService` was created but never became `Ready`:

```
$ kubectl -n default get inferenceservice sklearn-iris
NAME           URL   READY   PREV   LATEST   PREVROLLEDOUTREVISION   LATESTREADYREVISION   AGE
sklearn-iris         False          100                                                     8m
```

`READY=False` with no URL populated means the KServe controller did not complete ingress setup. No Knative Route was created. No external URL was assigned.

### Digging In

```
$ kubectl -n default describe inferenceservice sklearn-iris
...
Status:
  Conditions:
    Last Transition Time:  2026-01-20T11:30:00Z
    Message:               Failed to reconcile ingress
    Reason:                ReconcileError
    Status:                False
    Type:                  IngressReady
...

$ kubectl -n kserve logs deploy/kserve-controller-manager --tail=50
...
ERROR   controller.inferenceservice Failed to reconcile ingress
  {"error": "virtual service not found: sklearn-iris.default.svc.cluster.local"}
...
```

The error referenced a "virtual service" — that is an Istio concept. But we were running Kourier. The KServe controller was attempting to create an Istio `VirtualService` in a cluster that had no Istio control plane.

### Root Cause: Default KServe Ingress Mode Assumes Istio

KServe's default `inferenceservice-config` ConfigMap expects Istio as the ingress provider. It references `istio-ingressgateway.istio-system.svc.cluster.local` and sets `ingressClassName: istio`. When Istio is absent, the controller enters an error loop trying to create resources that will never exist.

The specific field that controls this is `disableIstioVirtualHost` in the `ingress` section of the ConfigMap — and it defaults to `false`, meaning "use Istio VirtualServices." Setting it to `true` tells KServe to skip Istio and fall back to standard Kubernetes Ingress or Knative route objects that Kourier can handle.

### The Fix: ConfigMap Patch in `serving-stack`

We added a Kustomize patch to override the ConfigMap:

```yaml
# infrastructure/serving-stack/patches/inferenceservice-config-ingress.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: inferenceservice-config
  namespace: kserve
data:
  ingress: |-
    {
      "ingressGateway": "knative-serving/knative-ingress-gateway",
      "ingressService": "istio-ingressgateway.istio-system.svc.cluster.local",
      "localGateway": "knative-serving/knative-local-gateway",
      "localGatewayService": "knative-local-gateway.istio-system.svc.cluster.local",
      "ingressDomain": "example.com",
      "ingressClassName": "istio",
      "domainTemplate": "{{ .Name }}-{{ .Namespace }}.{{ .IngressDomain }}",
      "urlScheme": "http",
      "disableIstioVirtualHost": true,
      "disableIngressCreation": false
    }
```

After this patch was applied and KServe controller restarted:

```
$ kubectl -n default get inferenceservice sklearn-iris
NAME           URL                                       READY   AGE
sklearn-iris   http://sklearn-iris.default.example.com  True    2m
```

### Business Impact

This failure cost approximately 3 hours. The KServe documentation does not prominently state that the default configuration requires Istio. The error message ("virtual service not found") is Istio-specific vocabulary that only makes sense if you already know Istio is the default — a classic undocumented assumption in infrastructure tooling.

**Why Kourier instead of Istio:** Istio adds approximately 1 GB of memory overhead across its control plane components. On a local k3d cluster with 8 GB RAM shared with Docker Desktop, Backstage, and the KServe controller, this would exhaust available memory and make the demo non-functional. Kourier's entire footprint is under 200 MB.

---

## Failure 2: ArgoCD Serving-Stack Sync Fails — Duplicate Knative CRD Exceeds 256 KB Annotation Size Limit

### Symptom

After the `inferenceservice-config` fix, the serving-stack ArgoCD app returned `SyncFailed`:

```
$ kubectl -n argocd get application serving-stack
NAME            SYNC STATUS   HEALTH STATUS
serving-stack   OutOfSync      Degraded

$ kubectl -n argocd describe application serving-stack
...
Message: one or more objects failed to apply, reason: 
  CustomResourceDefinition.apiextensions.k8s.io "services.serving.knative.dev" 
  is invalid: metadata.annotations: Too long: may not be more than 262144 bytes
```

The Knative `services.serving.knative.dev` CRD annotation was over the 256 KB limit because ArgoCD was trying to store the entire last-applied-configuration in the annotation — a common problem with large CRD objects.

### Root Cause

ArgoCD uses server-side apply for resources that contain `kubectl.kubernetes.io/last-applied-configuration`. For large CRDs, this annotation plus the apply payload exceeds Kubernetes' 256 KB annotation size limit. The Knative CRD is approximately 400 KB as a YAML object.

Additionally, there was a rendering overlap: the `kserve.yaml` bundle already includes its own version of the Knative Serving CRDs, and we were also referencing `serving-core.yaml` directly. This created two attempts to manage the same CRDs, causing comparison instability.

### Fix

Two changes in `infrastructure/serving-stack/kustomization.yaml`:

1. Added a `commonAnnotations` section to prevent ArgoCD from storing last-applied-configuration on CRD objects:
   ```yaml
   commonAnnotations:
     argocd.argoproj.io/sync-options: ServerSideApply=true
   ```

2. Added ignore-differences for KServe-managed Knative CRDs that are mutated at runtime by webhooks:
   ```yaml
   # In ArgoCD Application spec
   ignoreDifferences:
     - group: apiextensions.k8s.io
       kind: CustomResourceDefinition
       name: services.serving.knative.dev
       jsonPointers:
         - /spec/preserveUnknownFields
   ```

After these changes, serving-stack reached `Synced/Healthy`.

### Business Impact

30 minutes of confusion. ArgoCD's error message says "Too long" which points to the annotation, but does not tell you *which* annotation or *why* it got too long. Debugging requires knowing ArgoCD's internal apply mechanism.

---

## Failure 3: kube-rbac-proxy Sidecar ImagePullBackOff Blocks KServe Admission Webhook — gcr.io Registry Access Restriction

### Symptom

After the serving-stack was synced and the `InferenceService` showed `Ready=True`, subsequent Argo sync of the `ai-model-alpha` app failed with:

```
$ kubectl -n argocd get application ai-model-alpha
NAME             SYNC STATUS   HEALTH STATUS
ai-model-alpha   OutOfSync      Degraded

$ kubectl -n argocd describe application ai-model-alpha
...
Message: admission webhook "inferenceservice.kserve-webhook-server.validator.webhook" 
  denied the request: Internal error occurred: 
  no endpoints available for service "kserve-webhook-server-service"
```

The webhook endpoint was unavailable. The KServe controller pod was `1/2 Running`:

```
$ kubectl -n kserve get pods
NAME                                        READY   STATUS             RESTARTS
kserve-controller-manager-8d7c5b9f4-xr2lm  1/2     Running            0

$ kubectl -n kserve describe pod kserve-controller-manager-8d7c5b9f4-xr2lm
...
Containers:
  manager:
    Ready:          True
  kube-rbac-proxy:
    State:    Waiting
    Reason:   ImagePullBackOff
    Message:  Back-off pulling image "gcr.io/kubebuilder/kube-rbac-proxy:v0.13.1"
...
Events:
  Warning  Failed  2m  kubelet  
    Failed to pull image "gcr.io/kubebuilder/kube-rbac-proxy:v0.13.1": 
    rpc error: code = Unknown desc = failed to pull and unpack image: 
    failed to resolve reference "gcr.io/kubebuilder/kube-rbac-proxy:v0.13.1": 
    unexpected status code 403 Forbidden
```

### Root Cause

KServe 0.12.1's `kserve-controller-manager` Deployment includes a `kube-rbac-proxy` sidecar container that is referenced from `gcr.io/kubebuilder/kube-rbac-proxy:v0.13.1`. This image was no longer accessible — Google Container Registry (gcr.io) restricted access to kubebuilder images in late 2025.

The manager container itself was healthy and running (1 of 2 containers ready). But because the `kube-rbac-proxy` sidecar was not running, the webhook server certificate was not being served correctly, so the admission webhook had no healthy endpoints.

We tried the alternative registry `registry.k8s.io/kube-rbac-proxy:v0.13.1` — that tag did not exist at the new location either.

### Fix

Removed the `kube-rbac-proxy` sidecar entirely with a Kustomize strategic merge patch:

```yaml
# infrastructure/serving-stack/patches/kserve-controller-kube-rbac-proxy-image.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kserve-controller-manager
  namespace: kserve
spec:
  template:
    spec:
      containers:
        - name: kube-rbac-proxy
          $patch: delete
```

After this patch and a re-sync:

```
$ kubectl -n kserve get pods
NAME                                        READY   STATUS    RESTARTS
kserve-controller-manager-7b8c9d4f5-mn3kp  1/1     Running   0

$ kubectl -n kserve get endpoints kserve-webhook-server-service
NAME                           ENDPOINTS          AGE
kserve-webhook-server-service  10.42.0.23:9443    45s
```

The admission webhook was now functional. ArgoCD synced `ai-model-alpha` successfully.

### Known Tradeoff

Removing `kube-rbac-proxy` disables the Prometheus metrics proxy endpoint for the KServe controller. In a production environment, you would source a verified replacement image from a still-accessible registry. For this local lab, the tradeoff is acceptable: inference functionality and webhook admission work correctly; metrics scraping from the controller is unavailable.

### Business Impact

The `kube-rbac-proxy` image pull failure was an external dependency failure (registry access change) that cascaded into a complete admission webhook outage. Any `InferenceService` creation or update was blocked cluster-wide while the sidecar was failing. This is a class of failure that has no good solution without upstream monitoring of your image dependencies.

---

## Failure 4: Inference Request Returns HTTP 405 — IngressDomain Placeholder Resolves to Public Internet Instead of Local Cluster

### Symptom

After the `InferenceService` was `Ready=True`, the initial inference test returned unexpected results:

```
$ ISVC_URL=$(kubectl -n default get inferenceservice sklearn-iris -o jsonpath='{.status.url}')
$ echo $ISVC_URL
http://sklearn-iris.default.example.com

$ curl -sS \
  -H 'Content-Type: application/json' \
  -d '{"instances":[[5.1,3.5,1.4,0.2]]}' \
  "$ISVC_URL/v1/models/sklearn-iris:predict"
<!DOCTYPE html>
<html>
<head><title>405 Not Allowed</title></head>
...
```

A 405 from `example.com`. The request was hitting the public `example.com` server, not our Kourier gateway.

### Root Cause

The `ingressDomain` in the KServe ConfigMap was set to `example.com` — a literal domain used as a placeholder. The generated URL `sklearn-iris.default.example.com` resolves publicly to Cloudflare/IANA servers, not our local cluster. DNS resolution bypassed the local cluster entirely.

Additionally, Kourier routes by `Host` header, not by IP. Just port-forwarding Kourier and hitting `127.0.0.1` does not work unless you also pass the correct `Host` header.

### Fix

Direct port-forward to the predictor pod itself — this bypasses Knative routing and Kourier entirely and gives a deterministic local proof that the model server is functional:

```bash
# Get the predictor pod name
kubectl -n default get pods -l serving.knative.dev/revision=sklearn-iris-predictor-00001

# Port-forward to port 8080 on the predictor container
kubectl -n default port-forward pod/sklearn-iris-predictor-00001-deployment-<hash> 18080:8080

# Predict against the pod directly (no Host header needed)
curl -sS \
  -H "Content-Type: application/json" \
  -d '{"instances":[[5.1,3.5,1.4,0.2],[6.2,3.4,5.4,2.3]]}' \
  http://127.0.0.1:18080/v1/models/sklearn-iris:predict
```

Expected output:

```json
{"predictions":[0,2]}
```

For Kourier-path testing, pass the correct `Host` header:

```bash
kubectl -n kourier-system port-forward svc/kourier 18080:80

curl -sS \
  -H 'Host: sklearn-iris-predictor.default.127.0.0.1.sslip.io' \
  -H 'Content-Type: application/json' \
  -d '{"instances":[[5.1,3.5,1.4,0.2]]}' \
  http://127.0.0.1:18080/v1/models/sklearn-iris:predict
```

### Business Impact

False-negative inference verification. We had a healthy endpoint and thought it was broken because the test URL resolved to the wrong server. This wasted 1 hour of debugging. The lesson: always verify the complete network path (DNS resolution, ingress routing, pod health) as separate steps rather than assuming a single `curl` test is conclusive.

---

## What Milestone 2 Actually Proves (After the Failures)

After working through the above failures, the inference baseline worked:

```
$ kubectl -n default get inferenceservice sklearn-iris
NAME           URL                                       READY   AGE
sklearn-iris   http://sklearn-iris.default.example.com  True    45m

$ curl -sS \
  -H "Content-Type: application/json" \
  -d '{"instances":[[5.1,3.5,1.4,0.2],[6.2,3.4,5.4,2.3]]}' \
  http://127.0.0.1:18080/v1/models/sklearn-iris:predict
{"predictions":[0,2]}
```

**Interview-ready framing:** "The Istio/Kourier mismatch is the canonical example of why 'default configuration' is dangerous in complex systems. KServe's default assumes a specific network topology (Istio service mesh) that is not disclosed in the getting-started docs. Recognizing this class of failure — configuration that works in the tool author's environment but not yours — is a senior platform engineering competency."

---

## Debugging Commands Reference: KServe InferenceService Conditions, Webhook Endpoints, and Network Path Verification

```bash
# Check InferenceService ready status and conditions
kubectl -n default describe inferenceservice sklearn-iris

# Check KServe controller logs (most useful for reconciliation errors)
kubectl -n kserve logs deploy/kserve-controller-manager --tail=50
kubectl -n kserve logs deploy/kserve-controller-manager -c manager --tail=50

# Check webhook endpoint availability
kubectl -n kserve get endpoints kserve-webhook-server-service
kubectl -n kserve describe endpoints kserve-webhook-server-service

# Check Knative service and route status
kubectl -n default get ksvc
kubectl -n default get route

# Verify the inferenceservice-config ConfigMap contents
kubectl -n kserve get configmap inferenceservice-config -o yaml

# Check all pod container statuses in kserve namespace
kubectl -n kserve get pods -o wide
kubectl -n kserve describe pod <pod-name>
```

---

## See Also

- `docs/WEEK_2_LEARNING_REVIEW.md` — milestone close-out and design decisions
- `infrastructure/serving-stack/patches/inferenceservice-config-ingress.yaml` — Kourier config patch
- `infrastructure/serving-stack/patches/kserve-controller-kube-rbac-proxy-image.yaml` — sidecar removal patch
- `infrastructure/kserve/sklearn-runtime.yaml` — ClusterServingRuntime definition
