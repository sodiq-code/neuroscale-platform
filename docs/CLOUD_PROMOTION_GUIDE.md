# Cloud Promotion Guide — NeuroScale

This document describes how to promote the NeuroScale platform from a local k3d
development cluster to a production-grade cloud cluster on EKS or GKE.

The GitOps-first architecture means that **the application manifests are already
production-ready**. What changes is the underlying cluster, network, and DNS/TLS
layer that the GitOps reconciler targets.

---

## 1. What stays the same

| Layer | Status |
|---|---|
| GitOps root app (`bootstrap/root-app.yaml`) | No changes needed |
| ApplicationSet + ArgoCD child apps | No changes needed |
| KServe InferenceService manifests | No changes needed |
| Kyverno admission policies | No changes needed |
| Backstage scaffolder template | No changes needed |
| Namespace ResourceQuota + LimitRange | No changes needed |
| OpenCost deployment | Minor: point at cloud billing API |
| CI workflow (schema, policy, cost delta) | No changes needed |

All manifests use `server: https://kubernetes.default.svc` (in-cluster), so they
are cluster-agnostic by design.

---

## 2. Phase 1 — Provision the cloud cluster

### Option A: EKS (AWS)

```hcl
# terraform/eks/main.tf  (sketch — expand per your org's standards)
module "eks" {
  source          = "terraform-aws-modules/eks/aws"
  version         = "~> 20.0"

  cluster_name    = "neuroscale-prod"
  cluster_version = "1.29"

  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets

  eks_managed_node_groups = {
    gpu_inference = {
      instance_types = ["g4dn.xlarge"]   # GPU nodes for inference
      min_size       = 1
      max_size       = 10
      desired_size   = 2
    }
    cpu_control = {
      instance_types = ["m5.large"]      # CPU nodes for control-plane components
      min_size       = 2
      max_size       = 6
      desired_size   = 3
    }
  }
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
  name    = "neuroscale-prod"
  cidr    = "10.0.0.0/16"
  azs     = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  enable_nat_gateway = true
}
```

Key EKS add-ons required before bootstrapping ArgoCD:

```bash
# AWS Load Balancer Controller (replaces Kourier as the ingress provider)
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=neuroscale-prod

# EBS CSI driver (for PVC-backed model stores)
eksctl create addon --name aws-ebs-csi-driver --cluster neuroscale-prod
```

### Option B: GKE (GCP)

```hcl
# terraform/gke/main.tf
resource "google_container_cluster" "neuroscale_prod" {
  name     = "neuroscale-prod"
  location = "us-central1"

  # Separate node pool; remove default node pool
  remove_default_node_pool = true
  initial_node_count       = 1

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
}

resource "google_container_node_pool" "gpu_inference" {
  name       = "gpu-inference"
  cluster    = google_container_cluster.neuroscale_prod.name
  location   = "us-central1"

  autoscaling {
    min_node_count = 1
    max_node_count = 10
  }

  node_config {
    machine_type = "n1-standard-4"
    guest_accelerator {
      type  = "nvidia-tesla-t4"
      count = 1
    }
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}
```

---

## 3. Phase 2 — Bootstrap ArgoCD on the cloud cluster

The bootstrap process is the same as local, but targets the cloud cluster:

```bash
# Point kubectl at the new cluster
aws eks update-kubeconfig --name neuroscale-prod --region us-east-1
# or: gcloud container clusters get-credentials neuroscale-prod --region us-central1

# Run the existing bootstrap script unchanged
./scripts/bootstrap.sh
```

`bootstrap.sh` installs ArgoCD and applies `bootstrap/root-app.yaml`.  ArgoCD
then reconciles the entire stack from Git — no further manual steps.

### Repository access

Create an ArgoCD repository secret so it can pull from GitHub:

```bash
kubectl create secret generic neuroscale-repo \
  -n argocd \
  --from-literal=type=git \
  --from-literal=url=https://github.com/sodiq-code/neuroscale-platform.git \
  --from-literal=password="<github-pat>" \
  --from-literal=username=git \
  -l "argocd.argoproj.io/secret-type=repository"
```

---

## 4. Phase 3 — Replace Kourier with a cloud-native ingress

Local k3d uses Kourier (lightweight Envoy, port-forward only).  On a cloud
cluster, replace it with a production ingress that provides a stable external IP
and DNS.

### 4a. Swap ingress class in the serving-stack patch

```yaml
# infrastructure/serving-stack/patches/inferenceservice-config-ingress.yaml
data:
  ingress: |
    {
      "ingressClassName": "alb",          # AWS: use "nginx" or "alb"
      "disableIstioVirtualHost": "true"   # keep; Istio is not required
    }
```

For GKE, use `"ingressClassName": "gce"` or deploy the NGINX ingress controller.

### 4b. Annotate the Knative gateway service

```yaml
# infrastructure/serving-stack/patches/kourier-service-patch.yaml
apiVersion: v1
kind: Service
metadata:
  name: kourier
  namespace: kourier-system
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "external"
    service.beta.kubernetes.io/aws-load-balancer-scheme: "internet-facing"
spec:
  type: LoadBalancer
```

After ArgoCD syncs, note the external hostname:

```bash
kubectl get svc -n kourier-system kourier \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
# e.g. a1b2c3d4e5f6.us-east-1.elb.amazonaws.com
```

---

## 5. Phase 4 — DNS

Create a wildcard DNS record that points to the load balancer hostname.  KServe
generates endpoint URLs of the form
`<service>.<namespace>.svc.cluster.local` for in-cluster traffic and
`<service>.<namespace>.<ingress-domain>` for external traffic.

```
# Route 53 (AWS) or Cloud DNS (GCP)
*.inference.neuroscale.example.com  CNAME  <elb-hostname>
```

Update the KServe ingress domain config:

```yaml
# infrastructure/serving-stack/patches/inferenceservice-config-ingress.yaml
data:
  ingress: |
    {
      "ingressGateway": "kourier-internal.kourier-system.svc.cluster.local",
      "ingressGatewayServiceName": "kourier",
      "localGateway": "kourier-internal.kourier-system.svc.cluster.local",
      "localGatewayServiceName": "kourier-internal",
      "ingressDomain": "inference.neuroscale.example.com",
      "ingressClassName": "alb",
      "disableIstioVirtualHost": "true"
    }
```

After applying, InferenceService status will surface the external URL:

```bash
kubectl get inferenceservice ai-model-alpha \
  -o jsonpath='{.status.url}'
# https://ai-model-alpha.default.inference.neuroscale.example.com
```

---

## 6. Phase 5 — TLS on inference endpoints

### Option A: cert-manager (recommended)

```bash
# Install cert-manager via Helm (add to bootstrap if not present)
helm install cert-manager jetstack/cert-manager \
  -n cert-manager --create-namespace \
  --set installCRDs=true
```

Create a `ClusterIssuer` backed by Let's Encrypt:

```yaml
# infrastructure/cert-manager/cluster-issuer.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: platform-team@neuroscale.example.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            class: alb    # or "nginx"/"gce"
```

Annotate the ingress (or the Kourier `Service`) to request a certificate
automatically:

```yaml
metadata:
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
```

### Option B: ACM (AWS-managed TLS, no cert-manager)

```yaml
metadata:
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-ssl-cert: "arn:aws:acm:us-east-1:123456789012:certificate/<id>"
    service.beta.kubernetes.io/aws-load-balancer-ssl-ports: "443"
    service.beta.kubernetes.io/aws-load-balancer-backend-protocol: "http"
```

KServe serves plain HTTP internally; TLS is terminated at the ALB.

---

## 7. Phase 6 — Production Backstage

Switch Backstage from the dev values profile to prod:

```yaml
# infrastructure/apps/backstage-app.yaml — update valueFiles
spec:
  source:
    helm:
      valueFiles:
        - values.yaml
        - values-prod.yaml    # adds GitHub OAuth, HA replicas, real ingress host
```

`values-prod.yaml` already exists at `infrastructure/backstage/values-prod.yaml`
with GitHub OAuth configured.  Set the `GITHUB_CLIENT_ID` and
`GITHUB_CLIENT_SECRET` as Kubernetes secrets (or via Sealed Secrets / External
Secrets Operator) before syncing.

---

## 8. Phase 7 — OpenCost cloud billing integration

On a cloud cluster, OpenCost can pull real cost data from the cloud provider's
billing API instead of estimating from on-demand prices.

```yaml
# infrastructure/opencost/values.yaml  (additions)
opencost:
  cloudProviderApiKey: ""          # AWS: leave empty; use IRSA instead
  aws:
    spot_instance_enabled: true
    spot_data_bucket: "neuroscale-cost-data"
    spot_data_prefix: "spot-feed"
```

For EKS, attach an IAM role to the OpenCost service account via IRSA so it can
read the AWS Cost and Usage Report without static credentials.

---

## 9. Promotion checklist

Use this checklist when cutting a production release:

```
[ ] Terraform plan reviewed and applied (VPC + cluster + node pools)
[ ] bootstrap.sh run against production kubeconfig
[ ] ArgoCD ApplicationSet syncing all apps/* folders
[ ] Kourier/ALB service has stable external hostname
[ ] Wildcard DNS record created for inference.neuroscale.example.com
[ ] cert-manager ClusterIssuer healthy; InferenceService URLs are HTTPS
[ ] Backstage values-prod.yaml active; GitHub OAuth login works
[ ] Kyverno policies enforced (test: apply unlabeled InferenceService → expect deny)
[ ] OpenCost showing cost attribution by owner/cost-center labels
[ ] Namespace ResourceQuota + LimitRange confirmed on default namespace
[ ] CI workflow passing on main branch (schema + policy + cost-delta checks)
[ ] Branch protection enabled: require status checks, no force-push
```

---

## 10. What this does NOT cover (future work)

| Topic | Notes |
|---|---|
| Multi-region active-active | Requires cross-region ApplicationSets + global load balancing |
| Private cluster (VPC-internal) | Replace public ALB with internal NLB; add VPN/PrivateLink for Backstage |
| Secrets management | Integrate External Secrets Operator with AWS Secrets Manager / GCP Secret Manager |
| GPU autoscaling | Add KEDA or Knative autoscaling triggers on inference queue depth |
| Model registry | Integrate MLflow or Kubeflow Pipelines for model versioning before serving |
| Canary rollouts | Use Argo Rollouts alongside KServe traffic splitting for zero-downtime model updates |
