#!/usr/bin/env bash
# NeuroScale 2.0 — Inject a simulated failure into the demo
# Usage: bash agents/demo/inject_failure.sh [scenario]
# Scenarios: latency (default) | oom | drift | error_rate

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

SCENARIO="${1:-latency}"
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; RESET='\033[0m'

echo ""
echo -e "${RED}💥  Injecting failure scenario: ${SCENARIO}${RESET}"
echo ""

python3 - <<PYEOF
import sys, json
sys.path.insert(0, '.')
from agents.tools.arize_mcp import ArizeMCPClient

client = ArizeMCPClient()

scenarios = {
    "latency": {
        "model_id": "inference-engine",
        "metric": "latency_p99_ms",
        "value": 1850.0,
        "threshold": 800.0,
        "severity": "critical",
        "description": "P99 latency spike — HPA ceiling hit"
    },
    "oom": {
        "model_id": "feature-store",
        "metric": "memory_rss_bytes",
        "value": 3_900_000_000,
        "threshold": 2_147_483_648,
        "severity": "critical",
        "description": "OOM risk — memory approaching node limit"
    },
    "drift": {
        "model_id": "scoring-model-v3",
        "metric": "psi_score",
        "value": 0.35,
        "threshold": 0.20,
        "severity": "warning",
        "description": "Feature drift detected — retrain recommended"
    },
    "error_rate": {
        "model_id": "api-gateway",
        "metric": "http_5xx_rate",
        "value": 0.18,
        "threshold": 0.05,
        "severity": "critical",
        "description": "Error rate spike — pod crash-looping"
    },
}

s = scenarios.get("${SCENARIO}", scenarios["latency"])
result = client.inject_anomaly(s)
print(json.dumps(result, indent=2))
print()
print(f"  Scenario  : ${SCENARIO}")
print(f"  Service   : {s['model_id']}")
print(f"  Metric    : {s['metric']}")
print(f"  Value     : {s['value']}")
print(f"  Threshold : {s['threshold']}")
print()
print("  Run the orchestrator to trigger the pipeline:")
print("    python3 agents/orchestrator.py --inject")
PYEOF

echo ""
echo -e "${GREEN}✅  Failure injected. Orchestrator will detect on next poll.${RESET}"
echo ""
