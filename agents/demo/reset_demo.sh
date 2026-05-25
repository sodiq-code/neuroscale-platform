#!/usr/bin/env bash
# NeuroScale 2.0 — Reset demo state
# Clears injected anomalies and returns system to nominal state
# Usage: bash agents/demo/reset_demo.sh

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RESET='\033[0m'

echo ""
echo -e "${CYAN}🔄  Resetting NeuroScale demo state …${RESET}"
echo ""

python3 - <<PYEOF
import sys
sys.path.insert(0, '.')
from agents.tools.arize_mcp import ArizeMCPClient

client = ArizeMCPClient()

# Clear injected anomalies
if hasattr(client, '_injected_anomalies'):
    client._injected_anomalies.clear()

# Reset via tool call
result = client.call_tool("reset_demo", {})
print(f"  Arize state  : {result.get('status', 'reset')}")
PYEOF

echo -e "  GitLab MRs   : demo branches auto-cleaned (DEMO_MODE)"
echo -e "  RAG index    : unchanged (runbooks static)"
echo ""
echo -e "${GREEN}✅  Demo reset — system back to nominal baseline${RESET}"
echo -e "  Run ${CYAN}bash scripts/demo-run.sh${RESET} to start fresh"
echo ""
