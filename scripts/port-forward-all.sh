#!/usr/bin/env bash
# NeuroScale Platform — open every UI in one command
#
# Starts port-forwards for all NeuroScale UIs in background subshells, then
# prints a clickable summary table.  Press Ctrl+C (or q) to stop all tunnels.
#
# UIs opened:
#   https://localhost:8081   ArgoCD (GitOps dashboard)
#   http://localhost:7010    Backstage (developer portal + Golden Path)
#   http://localhost:9090    OpenCost (cost showback dashboard)
#   http://localhost:8082    Kourier (KServe inference gateway — not a browser UI)
#
# Usage: bash scripts/port-forward-all.sh [--no-wait]
#
# Options:
#   --no-wait   Print the summary immediately and exit (leave tunnels running in
#               the background).  Default: wait for Ctrl+C then kill all tunnels.

set -uo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

step()  { echo -e "\n${BOLD}${BLUE}▶ $1${NC}"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC}  $1"; }

NO_WAIT=false
for arg in "$@"; do
  [ "$arg" = "--no-wait" ] && NO_WAIT=true
done

# ── Prerequisite ──────────────────────────────────────────────────────────────
if ! kubectl cluster-info &>/dev/null; then
  echo -e "\n${RED}✗ Cannot reach the Kubernetes cluster.${NC}"
  echo "  Start cluster:  k3d cluster start neuroscale"
  echo "  Set context:    kubectl config use-context k3d-neuroscale"
  exit 1
fi

# ── Track child PIDs for clean shutdown ───────────────────────────────────────
PIDS=()

start_forward() {
  local label="$1"
  local ns="$2"
  local resource="$3"
  local port_map="$4"   # e.g. "8081:443"
  local local_port="${port_map%%:*}"

  # Check that the resource exists before trying to forward
  if ! kubectl -n "$ns" get "$resource" &>/dev/null 2>&1; then
    warn "${label}: resource '$resource' not found in namespace '$ns' — skipping"
    return
  fi

  kubectl -n "$ns" port-forward "$resource" "$port_map" \
    --address 127.0.0.1 >/dev/null 2>&1 &
  local pid=$!
  PIDS+=("$pid")

  # Give the tunnel a moment to bind
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    ok "${label} → port-forward running (PID ${pid})"
  else
    warn "${label} → port-forward failed to start (check namespace / resource name)"
  fi
}

# ── Open tunnels ──────────────────────────────────────────────────────────────
step "Opening port-forwards for all NeuroScale UIs"

start_forward "ArgoCD"    "argocd"          "svc/argocd-server"           "8081:443"
start_forward "Backstage" "backstage"       "svc/neuroscale-backstage"    "7010:7007"
start_forward "OpenCost"  "opencost"        "svc/opencost-ui"             "9090:9090"
start_forward "Kourier"   "kourier-system"  "svc/kourier"                 "8082:80"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  NeuroScale — All UIs Ready${NC}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  ┌────────────────┬────────────────────────────┬────────────────────────────────┐"
echo "  │ UI             │ URL                        │ Purpose                        │"
echo "  ├────────────────┼────────────────────────────┼────────────────────────────────┤"
echo "  │ ArgoCD         │ https://localhost:8081      │ GitOps dashboard — app health  │"
echo "  │ Backstage      │ http://localhost:7010       │ Developer portal + Golden Path │"
echo "  │ OpenCost       │ http://localhost:9090       │ Cost showback by owner/team    │"
echo "  │ Kourier        │ http://localhost:8082       │ KServe inference gateway       │"
echo "  └────────────────┴────────────────────────────┴────────────────────────────────┘"
echo ""

# ArgoCD admin password
ARGOCD_PASS=$(kubectl -n argocd \
  get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' 2>/dev/null | base64 -d 2>/dev/null || echo "<see kubectl -n argocd get secret argocd-initial-admin-secret>")

echo "  ArgoCD credentials:  admin / ${ARGOCD_PASS}"
echo ""
echo "  ┌─ Quick verification commands ─────────────────────────────────────────────┐"
echo "  │  bash scripts/smoke-test.sh --skip-drift --skip-policy-block             │"
echo "  │  kubectl -n argocd get applications                                       │"
echo "  │  kubectl -n default get inferenceservices                                 │"
echo "  │  kubectl -n default get resourcequota,limitrange                          │"
echo "  └───────────────────────────────────────────────────────────────────────────┘"
echo ""

if [ "${NO_WAIT}" = "true" ]; then
  echo -e "  ${YELLOW}--no-wait:${NC} tunnels running in the background. To stop them:"
  echo "    kill ${PIDS[*]:-<no PIDs>}"
  exit 0
fi

# ── Wait for Ctrl+C then cleanly kill all tunnels ─────────────────────────────
echo -e "  ${YELLOW}Press Ctrl+C to stop all port-forwards.${NC}"
echo ""

cleanup() {
  echo ""
  step "Stopping all port-forwards..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  echo -e "  ${GREEN}✓${NC} All tunnels stopped."
}
trap cleanup INT TERM

# Block until interrupted
wait "${PIDS[@]}" 2>/dev/null || true
