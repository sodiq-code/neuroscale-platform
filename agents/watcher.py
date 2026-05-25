"""
NeuroScale 2.0 — Watcher Agent
Phase 1 of the A2A pipeline.
Role: Continuously polls Arize Phoenix MCP for model metrics.
      Detects anomalies and compiles structured incident reports.
Model: Gemini Flash (speed-optimized for polling loop)
"""
from __future__ import annotations
import json, time
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import config
from tools.arize_mcp import ArizePhoenixMCPClient, SpanMetrics


class WatcherAgent:
    """
    Watcher Agent — Observability & Anomaly Detection.
    Equips: Arize Phoenix MCP tools (get_spans, get_trace).
    Output: Structured incident report JSON → Diagnostician Agent.
    """

    MODEL = "gemini-1.5-flash"  # Production: Gemini 3.5 Flash

    def __init__(self, arize_client: Optional[ArizePhoenixMCPClient] = None):
        self.arize = arize_client or ArizePhoenixMCPClient()
        self.models_to_watch = ["demo-iris-2", "ai-model-alpha"]

    def run_poll(self, model_name: str = "demo-iris-2") -> Optional[dict]:
        """
        Execute one polling cycle.
        Returns incident report dict if anomaly detected, None if healthy.
        """
        print(f"\n{'='*60}")
        print(f"  WATCHER AGENT — Polling Arize Phoenix")
        print(f"  Model: {model_name} | Time: {time.strftime('%H:%M:%S')}")
        print(f"{'='*60}")

        # MCP Tool call: get_spans
        metrics = self.arize.get_spans(model_name, window_minutes=10)

        if not metrics.is_anomalous:
            print(f"\n  ✅ WATCHER: {model_name} is healthy. No action required.")
            return None

        # Anomaly detected — get detailed trace for diagnosis
        print(f"\n  ⚠️  WATCHER: ANOMALY DETECTED on {model_name}")
        print(f"  {metrics.anomaly_description()}")

        # MCP Tool call: get_trace
        trace = self.arize.get_trace(f"trace-{model_name}-{int(time.time())}")

        # Build structured incident report for Diagnostician
        incident = {
            "incident_id": f"INC-{int(time.time())}",
            "model_name": model_name,
            "detected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "severity": self._classify_severity(metrics),
            "metrics": metrics.to_incident_report()["metrics"],
            "slo_breach": {
                "p99_latency_ms": metrics.p99_latency_ms,
                "threshold_ms": config.LATENCY_P99_THRESHOLD_MS,
                "error_rate_pct": metrics.error_rate_pct,
                "threshold_pct": config.ERROR_RATE_THRESHOLD_PCT,
            },
            "trace_sample": {
                "root_cause_hint": trace.get("root_cause_hint", ""),
                "failing_span": trace["spans"][0] if trace.get("spans") else {},
            },
            "agent_hypothesis": self._form_hypothesis(metrics, trace),
            "arize_dashboard_url": f"{config.ARIZE_PHOENIX_BASE_URL}/projects/neuroscale/spans",
        }

        print(f"\n  📋 WATCHER: Incident report compiled:")
        print(f"     ID: {incident['incident_id']}")
        print(f"     Severity: {incident['severity']}")
        print(f"     Hypothesis: {incident['agent_hypothesis']}")
        print(f"\n  → Handing off to Diagnostician Agent...")

        return incident

    def _classify_severity(self, metrics: SpanMetrics) -> str:
        if metrics.p99_latency_ms > 1000 or metrics.error_rate_pct > 10:
            return "CRITICAL"
        elif metrics.p99_latency_ms > 700 or metrics.error_rate_pct > 7:
            return "HIGH"
        else:
            return "MEDIUM"

    def _form_hypothesis(self, metrics: SpanMetrics, trace: dict) -> str:
        """Simple rule-based hypothesis formation (production: Gemini reasoning)."""
        hint = trace.get("root_cause_hint", "")
        if "cpu" in hint.lower() or "throttl" in hint.lower():
            return "CPU throttling on predictor pod — resource limits too low for current load"
        elif "drift" in hint.lower():
            return "Model drift detected — prediction distribution diverging from baseline"
        elif metrics.error_rate_pct > 10:
            return "High error rate — possible model version mismatch or serving runtime crash"
        elif metrics.p99_latency_ms > 800:
            return "P99 latency breach — likely CPU throttling or memory pressure on predictor"
        return "Unknown degradation — requires diagnostic reasoning from historical runbooks"


# ─── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== Watcher Agent — Self-Test ===\n")
    agent = WatcherAgent()

    print("Test 1: Healthy cluster (should return None)")
    result = agent.run_poll("demo-iris-2")
    assert result is None, f"Expected None for healthy cluster, got: {result}"
    print("  ✅ PASS: No incident reported for healthy cluster\n")

    print("Test 2: Anomalous cluster (inject failure, should return incident)")
    agent.arize.inject_anomaly("demo-iris-2")
    result = agent.run_poll("demo-iris-2")
    assert result is not None, "Expected incident report for anomalous cluster"
    assert "incident_id" in result
    assert result["severity"] in ("CRITICAL", "HIGH", "MEDIUM")
    print(f"\n  ✅ PASS: Incident {result['incident_id']} correctly reported")
    print(f"  Severity: {result['severity']}")
    print(f"  Hypothesis: {result['agent_hypothesis']}")
    print("\n✅ Watcher Agent self-test PASSED")
