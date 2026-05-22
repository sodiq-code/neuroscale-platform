# Copilot Moment 1: Architecture Decision — Kourier over Istio

## The Problem

KServe's `InferenceService` was stuck at `READY=False`. The controller logs showed:

```
ERROR  Failed to reconcile ingress
  {"error": "virtual service not found: sklearn-iris.default.svc.cluster.local"}
```

The error referenced Istio `VirtualService` objects — but we were running Kourier. The KServe controller was in an infinite error loop.

## Where Copilot Helped

This was not a "generate some code" moment. This was an architectural tradeoff evaluation.

**The question I asked Copilot:**

> "KServe InferenceService is stuck Not Ready. Error: 'virtual service not found'. We're running Kourier, not Istio. What's the architectural mismatch, and how do I fix it without adding Istio? Consider this is a local k3d cluster with 8GB RAM shared with Docker Desktop, Backstage, KServe controller, and ArgoCD."

**What Copilot helped me understand:**

1. KServe's default `inferenceservice-config` ConfigMap assumes Istio. The key field is `disableIstioVirtualHost` which defaults to `false`.

2. Setting `disableIstioVirtualHost: true` tells KServe to skip Istio VirtualService creation and fall back to Knative route objects that Kourier handles natively.

3. The memory tradeoff: Istio control plane adds ~1GB overhead. Kourier's entire footprint is under 200MB. On a constrained k3d cluster, this is the difference between a working demo and OOMKilled pods.

## The Fix

A Kustomize patch in `infrastructure/serving-stack/patches/inferenceservice-config-ingress.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: inferenceservice-config
  namespace: kserve
data:
  ingress: |-
    {
      "disableIstioVirtualHost": true,
      ...
    }
```

## The Result

```
$ kubectl get inferenceservice sklearn-iris
NAME           URL                                       READY   AGE
sklearn-iris   http://sklearn-iris.default.example.com   True    2m
```

Working inference endpoint. 800MB less memory. Reproducible on any dev machine.

## Why This Shows Judgment, Not Just Code Generation

Copilot didn't write a one-liner. It helped me evaluate an architectural tradeoff that had cascading implications:

- **Resource constraints** → Istio was not viable on local hardware
- **Ingress compatibility** → Kourier required specific KServe config changes
- **Documentation gap** → KServe docs don't prominently state Istio is assumed
- **Platform portability** → the fix works identically on k3d, Kind, and cloud clusters

This is the kind of decision where Copilot functions as a senior infrastructure advisor — not a code generator.
