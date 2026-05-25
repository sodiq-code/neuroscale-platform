#!/usr/bin/env bash
# ============================================================
# NeuroScale 2.0 — Full Verification Runner
# Runs every agent self-test and prints a pass/fail table
# Usage: bash scripts/verify-all.sh
# ============================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Colours
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

PASS=0
FAIL=0
declare -a RESULTS=()

run_test() {
  local label="$1"
  local cmd="$2"
  printf "  %-45s" "$label"
  if output=$(python3 $cmd 2>&1); then
    echo -e "${GREEN}✅ PASS${RESET}"
    RESULTS+=("PASS|$label")
    ((PASS++)) || true
  else
    echo -e "${RED}❌ FAIL${RESET}"
    echo -e "${RED}     ↳ $output${RESET}" | head -5
    RESULTS+=("FAIL|$label")
    ((FAIL++)) || true
  fi
}

echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}${BOLD}║       NeuroScale 2.0 — Verification Suite                    ║${RESET}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════════╝${RESET}"
echo ""

# ── Infrastructure ────────────────────────────────────────────────────────────
echo -e "${BOLD}  Infrastructure Layer${RESET}"
run_test "arize_mcp.py  (Arize Phoenix client)"  "agents/tools/arize_mcp.py"
run_test "gitlab_mcp.py (GitLab MCP client)"      "agents/tools/gitlab_mcp.py"
run_test "rag_store.py  (RAG / runbook search)"   "agents/tools/rag_store.py"
echo ""

# ── Agents ────────────────────────────────────────────────────────────────────
echo -e "${BOLD}  Agent Layer${RESET}"
run_test "watcher.py    (Watcher Agent)"           "agents/watcher.py"
run_test "diagnostician.py (Diagnostician Agent)"  "agents/diagnostician.py"
run_test "operator_agent.py (Operator Agent))"          "agents/operator_agent.py"
echo ""

# ── Orchestrator ──────────────────────────────────────────────────────────────
echo -e "${BOLD}  Orchestration Layer${RESET}"
run_test "orchestrator.py (Full A2A pipeline)"     "agents/orchestrator.py --self-test --quiet"
echo ""

# ── Summary table ─────────────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL))
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}${BOLD}║  Results: ${GREEN}${PASS}/${TOTAL} passed${CYAN}                                          ║${RESET}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════════╝${RESET}"
echo ""

if [[ $FAIL -gt 0 ]]; then
  echo -e "${RED}${BOLD}  Failed tests:${RESET}"
  for r in "${RESULTS[@]}"; do
    status="${r%%|*}"
    label="${r##*|}"
    if [[ "$status" == "FAIL" ]]; then
      echo -e "  ${RED}✗  $label${RESET}"
    fi
  done
  echo ""
  exit 1
else
  echo -e "${GREEN}${BOLD}  🎉 All tests passed — NeuroScale 2.0 is go for demo!${RESET}"
  echo ""
  exit 0
fi
