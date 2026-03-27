#!/usr/bin/env bash
# NeuroScale Platform — visual smoke test
#
# Tests every milestone end-to-end and reports PASS / FAIL / SKIP with
# colour-coded output. Run this on any laptop after bootstrapping the cluster.
#
# Usage: bash scripts/smoke-test.sh [--skip-drift] [--skip-policy-block]
#
# Options:
#   --skip-drift         Skip the GitOps drift self-heal test (avoids a ~60s
#                        wait; useful for a quick sanity check)
#   --skip-policy-block  Skip the live Kyverno admission-block test (useful
#                        when Kyverno is not yet healthy)

set -uo pipefail

# ── Options ───────────────────────────────────────────────────────────────────
SKIP_DRIFT=false
SKIP_POLICY_BLOCK=false

for arg in "$@"; do
  case "$arg" in
    --skip-drift)         SKIP_DRIFT=true ;;
    --skip-policy-block)  SKIP_POLICY_BLOCK=true ;;
  esac
done

# ── Colour / output helpers ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0

pass() { echo -e "  ${GREEN}[✓ PASS]${NC} $1"; PASS=$(( PASS + 1 )); }
fail() { echo -e "  ${RED}[✗ FAIL]${NC} $1"; FAIL=$(( FAIL + 1 )); }
skip() { echo -e "  ${YELLOW}[~ SKIP]${NC} $1"; SKIP=$(( SKIP + 1 )); }
info() { echo -e "         ${BLUE}↳${NC}  $1"; }
section() {
  echo ""
  echo -e "${BOLD}${BLUE}━━━ $1 ━━━${NC}"
}

# ── Prerequisites ─────────────────────────────────────────────────────────────
section "Prerequisites"

for cmd in kubectl curl; do
  if command -v "$cmd" &>/dev/null; then
    pass "$cmd available"
  else
    fail "$cmd not found on PATH"
  fi
done

if ! kubectl cluster-info &>/dev/null; then
  echo -e "\n${RED}✗ Cannot reach the Kubernetes cluster.${NC}"
  echo "  Start the cluster:  k3d cluster start neuroscale"
  echo "  Set context:        kubectl config use-context k3d-neuroscale"
  exit 1
fi
pass "kubectl can reach the cluster"

# ── Milestone A: GitOps spine (ArgoCD) ───────────────────────────────────────
section "Milestone A — GitOps Spine (ArgoCD)"

# ArgoCD pods
not_running=$(kubectl -n argocd get pods --no-headers 2>/dev/null \
  | awk '$3 != "Running" && $3 != "Completed" {print $1}' | wc -l || echo "99")

if [ "${not_running}" -eq 0 ]; then
  pass "All ArgoCD pods are Running"
else
  fail "${not_running} ArgoCD pod(s) are NOT Running"
  info "Diagnose: kubectl -n argocd get pods"
fi

# Applications
total_apps=$(kubectl -n argocd get applications --no-headers 2>/dev/null | wc -l || echo "0")
healthy_apps=$(kubectl -n argocd get applications --no-headers 2>/dev/null \
  | grep -c "Healthy" || echo "0")
synced_apps=$(kubectl -n argocd get applications --no-headers 2>/dev/null \
  | grep -c "Synced" || echo "0")

if [ "${total_apps}" -gt 0 ]; then
  if [ "${healthy_apps}" -eq "${total_apps}" ]; then
    pass "ArgoCD Applications: ${healthy_apps}/${total_apps} Healthy"
  else
    fail "ArgoCD Applications: ${healthy_apps}/${total_apps} Healthy (expected all Healthy)"
    info "Diagnose: kubectl -n argocd get applications"
  fi

  if [ "${synced_apps}" -eq "${total_apps}" ]; then
    pass "ArgoCD Applications: ${synced_apps}/${total_apps} Synced"
  else
    fail "ArgoCD Applications: ${synced_apps}/${total_apps} Synced"
    info "Force re-sync: kubectl -n argocd patch application <name> --type merge \\"
    info "  -p '{\"metadata\":{\"annotations\":{\"argocd.argoproj.io/refresh\":\"hard\"}}}'"
  fi
else
  fail "No ArgoCD Applications found"
  info "Apply root app: kubectl apply -f bootstrap/root-app.yaml"
fi

# Drift self-heal test
if [ "${SKIP_DRIFT}" = "true" ]; then
  skip "GitOps drift self-heal test (--skip-drift)"
else
  echo ""
  echo -e "  ${YELLOW}Running drift self-heal demo (deletes nginx-test, waits for recreation)...${NC}"
  if kubectl get deploy nginx-test -n default &>/dev/null; then
    kubectl delete deploy nginx-test -n default &>/dev/null || true
    info "Deleted nginx-test. Waiting up to 60 s for ArgoCD to recreate it..."
    recreated=false
    for i in $(seq 1 12); do
      sleep 5
      ready=$(kubectl get deploy nginx-test -n default \
        -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
      if [ "${ready:-0}" -ge 1 ]; then
        elapsed=$(( i * 5 ))
        pass "Drift self-heal: nginx-test recreated and Ready in ~${elapsed}s"
        recreated=true
        break
      fi
    done
    if [ "${recreated}" = "false" ]; then
      fail "Drift self-heal: nginx-test was NOT recreated within 60 s"
      info "Diagnose: kubectl -n argocd describe application test-app"
    fi
  else
    skip "Drift self-heal test (nginx-test deployment not found in default namespace)"
  fi
fi

# ── Milestone B: AI serving (KServe) ─────────────────────────────────────────
section "Milestone B — AI Serving Baseline (KServe)"

# KServe controller
kserve_avail=$(kubectl -n kserve get deploy kserve-controller-manager \
  -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")

if [ "${kserve_avail:-0}" -ge 1 ]; then
  pass "KServe controller-manager: ${kserve_avail} replica(s) available"
else
  fail "KServe controller-manager not ready"
  info "Diagnose: kubectl -n kserve get deploy kserve-controller-manager"
fi

# InferenceService status
isvc_total=$(kubectl -n default get inferenceservices --no-headers 2>/dev/null | wc -l || echo "0")
isvc_ready=$(kubectl -n default get inferenceservices --no-headers 2>/dev/null \
  | grep -c "True" || echo "0")

if [ "${isvc_total}" -gt 0 ]; then
  if [ "${isvc_ready}" -gt 0 ]; then
    pass "InferenceServices: ${isvc_ready}/${isvc_total} Ready=True"
  else
    fail "InferenceServices: 0/${isvc_total} Ready (none have Ready=True)"
    info "Diagnose: kubectl -n default get inferenceservices"
    info "Diagnose: kubectl -n kserve logs deploy/kserve-controller-manager --tail=20"
  fi
else
  fail "No InferenceServices found in namespace default"
fi

# Inference request via predictor pod port-forward
PREDICTOR_POD=$(kubectl -n default get pods --no-headers 2>/dev/null \
  | awk '/demo-iris-2.*Running/ {print $1}' | head -1 || echo "")

if [ -n "${PREDICTOR_POD:-}" ]; then
  echo ""
  echo -e "  ${YELLOW}Sending test inference request via port-forward...${NC}"
  kubectl -n default port-forward "pod/${PREDICTOR_POD}" 18080:8080 &>/dev/null &
  PF_PID=$!
  sleep 2

  PREDICT=$(curl -sS --max-time 10 \
    -H "Content-Type: application/json" \
    -d '{"instances":[[6.8,2.8,4.8,1.4],[6.0,3.4,4.5,1.6]]}' \
    http://127.0.0.1:18080/v1/models/demo-iris-2:predict 2>/dev/null || echo "FAILED")

  kill "${PF_PID}" 2>/dev/null || true
  wait "${PF_PID}" 2>/dev/null || true

  if echo "${PREDICT}" | grep -q '"predictions"'; then
    pass "Inference request: demo-iris-2 returned predictions"
    info "Response: ${PREDICT}"
  else
    fail "Inference request: demo-iris-2 did not return predictions"
    info "Response: ${PREDICT}"
    info "Pod:      ${PREDICTOR_POD}"
  fi
else
  skip "Inference request test (no Running pod matching demo-iris-2 found)"
  info "Ensure demo-iris-2 InferenceService is Ready=True before running this test"
fi

# ── Milestone C: Golden Path (Backstage) ─────────────────────────────────────
section "Milestone C — Golden Path (Backstage)"

# Backstage deployment
bs_avail=$(kubectl -n backstage get deploy neuroscale-backstage \
  -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")

if [ "${bs_avail:-0}" -ge 1 ]; then
  pass "Backstage deployment: ${bs_avail} replica(s) available"
else
  fail "Backstage deployment is not ready"
  info "Check: kubectl -n backstage get deploy neuroscale-backstage"
  info "Allow 3-4 minutes for startup probes to complete after first deploy"
fi

# Golden Path evidence: demo-iris-2 was created via Backstage scaffolder
if kubectl -n default get inferenceservice demo-iris-2 &>/dev/null; then
  pass "Golden Path evidence: demo-iris-2 InferenceService exists (scaffolder output)"
else
  fail "Golden Path evidence: demo-iris-2 InferenceService not found"
  info "Use Backstage at http://localhost:7010/create to run the Golden Path template"
fi

if kubectl -n argocd get application demo-iris-2 &>/dev/null; then
  pass "Golden Path evidence: demo-iris-2 ArgoCD Application exists (scaffolder output)"
else
  fail "Golden Path evidence: demo-iris-2 ArgoCD Application not found"
fi

# ── Milestone D: Guardrails (Kyverno) ────────────────────────────────────────
section "Milestone D — Guardrails (Kyverno + CI)"

# Kyverno pods
kyverno_running=$(kubectl -n kyverno get pods --no-headers 2>/dev/null \
  | grep -c "Running" || echo "0")

if [ "${kyverno_running:-0}" -ge 1 ]; then
  pass "Kyverno pods running: ${kyverno_running}"
else
  fail "No Kyverno pods running in namespace kyverno"
  info "Diagnose: kubectl -n kyverno get pods"
fi

# ClusterPolicies
policy_count=$(kubectl get clusterpolicies --no-headers 2>/dev/null | wc -l || echo "0")
if [ "${policy_count:-0}" -ge 3 ]; then
  pass "Kyverno ClusterPolicies installed: ${policy_count} policies"
else
  fail "Expected ≥ 3 Kyverno ClusterPolicies, found ${policy_count}"
  info "Diagnose: kubectl get clusterpolicies"
fi

# Admission block test (applies a non-compliant InferenceService; expects denial)
if [ "${SKIP_POLICY_BLOCK}" = "true" ]; then
  skip "Admission block test (--skip-policy-block)"
else
  echo ""
  echo -e "  ${YELLOW}Testing Kyverno admission block (applies non-compliant manifest)...${NC}"
  block_result=$(kubectl apply -f - 2>&1 <<'YAML' || true
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: smoke-test-bad-model
  namespace: default
spec:
  predictor:
    model:
      modelFormat:
        name: sklearn
      storageUri: "gs://kfserving-examples/models/sklearn/1.0/model"
YAML
)

  if echo "${block_result}" | grep -qiE "denied|blocked|admission webhook"; then
    pass "Admission block: non-compliant InferenceService correctly denied by Kyverno"
    info "Denial message: $(echo "${block_result}" | head -1)"
  elif echo "${block_result}" | grep -qiE "created|configured"; then
    fail "Admission block: non-compliant InferenceService was ALLOWED (expected denial)"
    info "Cleaning up accidentally created resource..."
    kubectl delete inferenceservice smoke-test-bad-model -n default &>/dev/null || true
  else
    fail "Admission block: unexpected result from kubectl apply"
    info "Output: ${block_result}"
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  NeuroScale Smoke Test — Results${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${GREEN}PASS${NC}  ${PASS}"
echo -e "  ${RED}FAIL${NC}  ${FAIL}"
echo -e "  ${YELLOW}SKIP${NC}  ${SKIP}"
echo ""

if [ "${FAIL}" -eq 0 ]; then
  echo -e "${GREEN}${BOLD}✓ All checks passed. Platform is healthy and ready to demo.${NC}"
  exit 0
else
  echo -e "${RED}${BOLD}✗ ${FAIL} check(s) failed. Review the output above for details.${NC}"
  exit 1
fi
