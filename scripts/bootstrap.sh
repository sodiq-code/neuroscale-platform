#!/usr/bin/env bash
# NeuroScale Platform — one-shot bootstrap
#
# Provisions a local k3d cluster, installs ArgoCD, and applies the NeuroScale
# root app-of-apps so every platform component converges from Git automatically.
#
# Usage: bash scripts/bootstrap.sh
#
# Prerequisites: Docker Desktop (running), k3d, kubectl, helm
# Estimated time: 5–8 minutes on a first run.

set -euo pipefail

CLUSTER_NAME="neuroscale"
ARGOCD_NAMESPACE="argocd"
ARGOCD_INSTALL_URL="https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml"

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

step()  { echo -e "\n${BOLD}${BLUE}[$(date +%H:%M:%S)] ▶ $1${NC}"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC}  $1"; }
die()   { echo -e "  ${RED}✗ ERROR:${NC} $1" >&2; exit 1; }

# ── Prerequisites ─────────────────────────────────────────────────────────────
step "Checking prerequisites"

require_cmd() {
  local cmd="$1" hint="$2"
  if command -v "$cmd" &>/dev/null; then
    ok "$cmd  →  $(command -v "$cmd")"
  else
    die "'$cmd' is not installed or not on PATH.\n  $hint"
  fi
}

require_cmd docker  "Install Docker Desktop: https://www.docker.com/products/docker-desktop"
require_cmd k3d     "Install k3d: curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash"
require_cmd kubectl "Install kubectl: https://kubernetes.io/docs/tasks/tools/"
require_cmd helm    "Install Helm: https://helm.sh/docs/intro/install/"

if ! docker info &>/dev/null; then
  die "Docker daemon is not running. Start Docker Desktop first and wait until it is fully ready."
fi
ok "Docker daemon is running"

# ── Cluster ───────────────────────────────────────────────────────────────────
step "Provisioning k3d cluster '${CLUSTER_NAME}'"

if k3d cluster list 2>/dev/null | grep -qE "^${CLUSTER_NAME}\b"; then
  warn "Cluster '${CLUSTER_NAME}' already exists — starting it if stopped."
  k3d cluster start "${CLUSTER_NAME}" 2>/dev/null || true
else
  echo "  Creating cluster (this takes ~60 seconds)..."
  k3d cluster create "${CLUSTER_NAME}" \
    --port "8081:443@loadbalancer" \
    --port "8082:80@loadbalancer"  \
    --k3s-arg "--disable=traefik@server:0" \
    --wait
  ok "Cluster '${CLUSTER_NAME}' created"
fi

kubectl config use-context "k3d-${CLUSTER_NAME}" &>/dev/null
ok "kubectl context → k3d-${CLUSTER_NAME}"

echo "  Waiting for cluster node to be Ready..."
kubectl wait --for=condition=Ready node --all --timeout=90s &>/dev/null
ok "All cluster nodes are Ready"

# ── ArgoCD ────────────────────────────────────────────────────────────────────
step "Installing ArgoCD (stable)"

kubectl create namespace "${ARGOCD_NAMESPACE}" --dry-run=client -o yaml \
  | kubectl apply -f - &>/dev/null

if kubectl -n "${ARGOCD_NAMESPACE}" get deploy argocd-server &>/dev/null; then
  warn "ArgoCD is already installed — skipping re-install."
else
  echo "  Applying ArgoCD manifests..."
  kubectl apply -n "${ARGOCD_NAMESPACE}" -f "${ARGOCD_INSTALL_URL}"
  ok "ArgoCD manifests applied"
fi

echo "  Waiting for ArgoCD server (up to 3 minutes)..."
kubectl -n "${ARGOCD_NAMESPACE}" wait \
  --for=condition=available deploy/argocd-server \
  --timeout=180s &>/dev/null

echo "  Waiting for ArgoCD repo-server (up to 3 minutes)..."
kubectl -n "${ARGOCD_NAMESPACE}" wait \
  --for=condition=available deploy/argocd-repo-server \
  --timeout=180s &>/dev/null

ok "ArgoCD is Ready"

# ── Root app ──────────────────────────────────────────────────────────────────
step "Applying NeuroScale root app-of-apps"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

kubectl apply -f "${REPO_ROOT}/bootstrap/root-app.yaml"
ok "Applied: bootstrap/root-app.yaml"

# ── ArgoCD admin password ─────────────────────────────────────────────────────
ARGOCD_PASS=$(kubectl -n "${ARGOCD_NAMESPACE}" \
  get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' 2>/dev/null | base64 -d 2>/dev/null || echo "<not available yet>")

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${GREEN}  Bootstrap complete!${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BOLD}ArgoCD is converging — allow 2–5 minutes for all apps to sync.${NC}"
echo ""
echo "  ┌─ Open the ArgoCD UI ─────────────────────────────────────────────┐"
echo "  │  kubectl port-forward svc/argocd-server -n argocd 8081:443      │"
echo "  │  Open: https://localhost:8081                                     │"
echo "  │  Username: admin                                                  │"
echo "  │  Password: ${ARGOCD_PASS}"
echo "  └───────────────────────────────────────────────────────────────────┘"
echo ""
echo "  ┌─ Open the Kourier inference gateway ─────────────────────────────┐"
echo "  │  kubectl -n kourier-system port-forward svc/kourier 8082:80      │"
echo "  └───────────────────────────────────────────────────────────────────┘"
echo ""
echo "  ┌─ Open Backstage ─────────────────────────────────────────────────┐"
echo "  │  kubectl -n backstage port-forward svc/neuroscale-backstage      │"
echo "  │    7010:7007                                                      │"
echo "  │  Open: http://localhost:7010/create                               │"
echo "  │                                                                   │"
echo "  │  Backstage needs a GitHub token to open PRs:                     │"
echo "  │    read -s GITHUB_TOKEN                                           │"
echo "  │    kubectl create ns backstage --dry-run=client -o yaml \\        │"
echo "  │      | kubectl apply -f -                                         │"
echo "  │    kubectl -n backstage create secret generic \\                   │"
echo "  │      neuroscale-backstage-secrets \\                               │"
echo "  │      --from-literal=GITHUB_TOKEN=\"\$GITHUB_TOKEN\" \\               │"
echo "  │      --dry-run=client -o yaml | kubectl apply -f -               │"
echo "  └───────────────────────────────────────────────────────────────────┘"
echo ""
echo "  ┌─ Run the smoke test ─────────────────────────────────────────────┐"
echo "  │  bash scripts/smoke-test.sh                                      │"
echo "  └───────────────────────────────────────────────────────────────────┘"
echo ""
