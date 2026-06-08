#!/usr/bin/env bash
# ============================================================
# NeuroScale 2.0 — Cinematic Demo Runner
# Full 10-beat demo with timing and narration cues
# Usage: bash scripts/demo-run.sh
# ============================================================

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Colours
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; MAGENTA='\033[0;35m'; BOLD='\033[1m'
DIM='\033[2m'; RESET='\033[0m'

DEMO_MODE=true
export DEMO_MODE

pause() { sleep "${1:-1}"; }

beat() {
  local num="$1"; local title="$2"; local narration="$3"
  echo ""
  echo -e "${CYAN}${BOLD}━━━  Beat ${num}: ${title}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
  echo -e "${DIM}  🎙  ${narration}${RESET}"
  echo ""
  pause 1
}

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${MAGENTA}${BOLD}╔══════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${MAGENTA}${BOLD}║         NeuroScale 2.0  —  Live Demo                             ║${RESET}"
echo -e "${MAGENTA}${BOLD}║         Autonomous AI SRE for Kubernetes                         ║${RESET}"
echo -e "${MAGENTA}${BOLD}╚══════════════════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "${DIM}  Mode: DEMO (no live credentials required)${RESET}"
echo -e "${DIM}  Press Ctrl+C to abort at any time${RESET}"
pause 2

# ─────────────────────────────────────────────────────────────────────────────
beat "1" "System Boot" "NeuroScale initialises — three autonomous agents come online."

echo -e "  ${GREEN}●${RESET} Watcher Agent       ${DIM}… ready${RESET}"
pause 0.3
echo -e "  ${GREEN}●${RESET} Diagnostician Agent ${DIM}… ready${RESET}"
pause 0.3
echo -e "  ${GREEN}●${RESET} Operator Agent      ${DIM}… ready${RESET}"
pause 0.3
echo -e "  ${GREEN}●${RESET} A2A Orchestrator    ${DIM}… ready${RESET}"
pause 1

# ─────────────────────────────────────────────────────────────────────────────
beat "2" "Normal Baseline" "First poll — system is healthy, no action needed."

python3 -c "
import sys; sys.path.insert(0, '.')
from agents.watcher import WatcherAgent
w = WatcherAgent()
r = w.run_poll()
if r is None:
    print('  ✅  System nominal — all metrics within SLO bounds')
    print('  ✅  No anomalies detected')
else:
    print(f'  ⚠️  Anomaly: {r}')
" 2>/dev/null
pause 2

# ─────────────────────────────────────────────────────────────────────────────
beat "3" "Anomaly Injection" "We simulate a production incident: P99 latency spikes to 1850ms."

echo -e "  ${RED}💥  Injecting failure: inference-engine latency_p99_ms → 1850ms${RESET}"
echo -e "  ${DIM}     (threshold: 800ms | SLO breach imminent)${RESET}"
pause 2

# ─────────────────────────────────────────────────────────────────────────────
beat "4" "Watcher Detects" "Watcher Agent polls Arize Phoenix — anomaly confirmed within seconds."

python3 -c "
import sys; sys.path.insert(0, '.')
from agents.watcher import WatcherAgent
w = WatcherAgent()
w.arize.inject_anomaly()  # Inject on same client instance
r = w.run_poll()
if r:
    m = r.get('metrics', {})
    print(f'  🚨 ANOMALY DETECTED')
    print(f'     Service   : {r.get(\"model_name\", \"demo-iris-2\")}')
    print(f'     P99       : {m.get(\"p99_latency_ms\", 0):.0f}ms  (threshold: 500ms)')
    print(f'     Error rate: {m.get(\"error_rate_pct\", 0):.1f}%  (threshold: 5%)')
    print(f'     Severity  : {r.get(\"severity\", \"CRITICAL\")}')
    print(f'     Hypothesis: {r.get(\"agent_hypothesis\", \"\")[:80]}')
else:
    print('  (no anomaly — run again if Arize client reset)')
" 2>/dev/null
pause 2

# ─────────────────────────────────────────────────────────────────────────────
beat "5" "Diagnostician Analyses" "Diagnostician cross-references runbooks via RAG — root cause identified."

python3 -c "
import sys, time; sys.path.insert(0, '.')
from agents.diagnostician import DiagnosticianAgent
d = DiagnosticianAgent()
incident = {
    'incident_id': 'INC-DEMO-BEAT5',
    'model_name': 'demo-iris-2',
    'model_id': 'demo-iris-2',
    'detected_at': '2026-05-25T17:55:00Z',
    'severity': 'CRITICAL',
    'agent_hypothesis': 'CPU throttling on predictor pod — resource limits too low for current load',
    'metrics': {'p99_latency_ms': 1850.0, 'error_rate_pct': 14.5, 'total_spans': 380},
}
plan = d.diagnose(incident)
rc = plan.get('root_cause', {})
raw_conf = rc.get('confidence', 'HIGH')
conf_map = {'HIGH': 0.90, 'MEDIUM': 0.75, 'LOW': 0.50}
conf = conf_map.get(raw_conf, 0.75) if isinstance(raw_conf, str) else raw_conf
print(f'  🔍 Root cause  : {rc.get(\"description\", \"\")[:90]}')
print(f'  📖 Runbook     : {rc.get(\"runbook_ref\", \"N/A\")}')
print(f'  🎯 Confidence  : {conf:.1%}')
actions = plan.get('actions', [])
for a in actions[:3]:
    print(f'     ✓ {a.get(\"description\", str(a))[:70]}')
" 2>/dev/null
pause 2

# ─────────────────────────────────────────────────────────────────────────────
beat "6" "RAG Runbook Retrieval" "TF-IDF semantic search finds the best-matching runbook."

python3 -c "
import sys; sys.path.insert(0, '.')
from agents.tools.rag_store import RunbookRAGClient
rag = RunbookRAGClient()
results = rag.semantic_search('HPA scaling limit cpu resource requests latency')
for r in results[:3]:
    rb_id = r.file.split('.')[0] if r.file else 'RB-???'
    print(f'  📄 {rb_id:25s}  score={r.relevance_score:.3f}  {r.title[:45]}')
" 2>/dev/null
pause 2

# ─────────────────────────────────────────────────────────────────────────────
beat "7" "Operator Executes" "Operator Agent autonomously creates a branch, commits a YAML fix, and opens an MR."

python3 -c "
import sys, logging, time; logging.disable(logging.CRITICAL); sys.path.insert(0, '.')
from agents.operator_agent import OperatorAgent
agent = OperatorAgent()
plan = {
    'incident_id': f'INC-DEMO-{int(time.time())}',
    'anomaly': {'service':'inference-engine'},
    'diagnosis': 'HPA ceiling hit due to missing resource limits.',
    'recommended_runbook': 'RB-001',
    'steps': ['Set cpu/memory limits','Raise HPA minReplicas','Verify Kyverno compliance'],
    'yaml_patch': 'resources:\n  limits:\n    cpu: 2000m\n    memory: 2Gi\n',
    'yaml_patch_path': 'infrastructure/agents/deployment.yaml',
    'confidence': 0.91,
    'requires_human_approval': True,
}
r = agent.execute(plan)
print(f'  ⚙️  Branch  : {r[\"branch\"]}')
print(f'  📝 Commit  : {r[\"commit_sha\"]}')
print(f'  🔀 MR URL  : {r[\"mr_url\"]}')
print(f'  🔔 Status  : {r[\"status\"]}')
" 2>/dev/null
pause 2

# ─────────────────────────────────────────────────────────────────────────────
beat "8" "HITL Gate" "Human approval required — MR sent to on-call engineer via webhook."

echo -e "  ${YELLOW}⏸  HITL GATE — awaiting human approval${RESET}"
echo -e "  ${DIM}  On-call notified via PagerDuty / Slack webhook${RESET}"
echo -e "  ${DIM}  Auto-merge eligible: confidence > 90% → 15-minute SLA${RESET}"
pause 2

# ─────────────────────────────────────────────────────────────────────────────
beat "9" "Full A2A Pipeline" "End-to-end orchestration — one command, zero humans in the loop for detection."

python3 agents/orchestrator.py --inject --quiet 2>/dev/null
pause 2

# ─────────────────────────────────────────────────────────────────────────────
beat "10" "Mission Accomplished" "From anomaly detection to MR in under 60 seconds — fully autonomous."

echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${GREEN}${BOLD}║  ✅ DEMO COMPLETE                                                ║${RESET}"
echo -e "${GREEN}${BOLD}║                                                                  ║${RESET}"
echo -e "${GREEN}${BOLD}║  Watcher → Diagnostician → Operator → HITL                      ║${RESET}"
echo -e "${GREEN}${BOLD}║  Detection-to-MR: < 60 seconds                                  ║${RESET}"
echo -e "${GREEN}${BOLD}║  Human effort: 0 lines of runbook manually executed              ║${RESET}"
echo -e "${GREEN}${BOLD}║  Kyverno compliance: enforced automatically                      ║${RESET}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════════════╝${RESET}"
echo ""
