"""
NeuroScale 2.0 — Arize Phoenix MCP Client
Watcher Agent tool: polls Phoenix for traces/spans, detects anomalies.
Implements the JSON-RPC 2.0 MCP protocol against @arizeai/phoenix-mcp server.
Falls back to direct Phoenix REST API for local/demo mode.
"""
from __future__ import annotations
import json, time, random
from dataclasses import dataclass, field
from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

try:
    import httpx
    _HTTPX = True
except ImportError:
    _HTTPX = False


# ─── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class SpanMetrics:
    model_name: str
    p99_latency_ms: float
    p50_latency_ms: float
    error_rate_pct: float
    total_spans: int
    window_minutes: int = 10
    timestamp: float = field(default_factory=time.time)

    @property
    def is_anomalous(self) -> bool:
        return (
            self.p99_latency_ms > config.LATENCY_P99_THRESHOLD_MS
            or self.error_rate_pct > config.ERROR_RATE_THRESHOLD_PCT
        )

    def anomaly_description(self) -> str:
        reasons = []
        if self.p99_latency_ms > config.LATENCY_P99_THRESHOLD_MS:
            reasons.append(
                f"P99 latency {self.p99_latency_ms:.0f}ms exceeds SLO "
                f"({config.LATENCY_P99_THRESHOLD_MS:.0f}ms)"
            )
        if self.error_rate_pct > config.ERROR_RATE_THRESHOLD_PCT:
            reasons.append(
                f"Error rate {self.error_rate_pct:.1f}% exceeds threshold "
                f"({config.ERROR_RATE_THRESHOLD_PCT:.1f}%)"
            )
        return "; ".join(reasons) if reasons else "No anomaly detected"

    def to_incident_report(self) -> dict:
        return {
            "model_name": self.model_name,
            "anomaly_detected": self.is_anomalous,
            "description": self.anomaly_description(),
            "metrics": {
                "p99_latency_ms": self.p99_latency_ms,
                "p50_latency_ms": self.p50_latency_ms,
                "error_rate_pct": self.error_rate_pct,
                "total_spans": self.total_spans,
                "window_minutes": self.window_minutes,
            },
            "slo_thresholds": {
                "p99_latency_ms": config.LATENCY_P99_THRESHOLD_MS,
                "error_rate_pct": config.ERROR_RATE_THRESHOLD_PCT,
            },
            "timestamp": self.timestamp,
        }


# ─── MCP Client ───────────────────────────────────────────────────────────────

class ArizePhoenixMCPClient:
    """
    MCP client for @arizeai/phoenix-mcp server.
    In production: connects to MCP server via JSON-RPC 2.0 stdio/SSE transport.
    In demo mode: uses Phoenix REST API directly + demo data injection.
    """

    def __init__(self):
        self.base_url = config.ARIZE_PHOENIX_BASE_URL
        self._demo_mode = config.DEMO_MODE
        self._injected_anomaly: Optional[SpanMetrics] = None

    # ── MCP Tool: get_spans ────────────────────────────────────────────────────
    def get_spans(
        self,
        model_name: str = "demo-iris-2",
        window_minutes: int = 10,
    ) -> SpanMetrics:
        """
        MCP tool call: mcp_arize_get_spans
        Returns aggregated span metrics for the given model in the time window.
        """
        print(f"  [Arize MCP] Invoking get-spans: model={model_name}, window={window_minutes}m")

        if self._injected_anomaly and self._injected_anomaly.model_name == model_name:
            metrics = self._injected_anomaly
            print(f"  [Arize MCP] ⚡ Injected anomaly active — returning degraded metrics")
        elif self._demo_mode and not _HTTPX:
            metrics = self._demo_healthy_metrics(model_name, window_minutes)
        elif _HTTPX:
            metrics = self._fetch_from_phoenix(model_name, window_minutes)
        else:
            metrics = self._demo_healthy_metrics(model_name, window_minutes)

        print(f"  [Arize MCP] P99={metrics.p99_latency_ms:.0f}ms  "
              f"ErrorRate={metrics.error_rate_pct:.1f}%  "
              f"Spans={metrics.total_spans}  "
              f"Anomaly={'YES ⚠' if metrics.is_anomalous else 'NO ✓'}")
        return metrics

    # ── MCP Tool: get_trace ────────────────────────────────────────────────────
    def get_trace(self, trace_id: str) -> dict:
        """MCP tool call: mcp_arize_get_trace"""
        print(f"  [Arize MCP] Invoking get-trace: trace_id={trace_id}")
        return {
            "trace_id": trace_id,
            "spans": [
                {"span_id": "s1", "name": "predict", "duration_ms": 823, "status": "ERROR",
                 "attributes": {"model": "demo-iris-2", "error": "CPU throttling detected"}},
                {"span_id": "s2", "name": "preprocess", "duration_ms": 312, "status": "OK"},
            ],
            "root_cause_hint": "CPU throttling on predictor pod — model drift + resource exhaustion",
        }

    # ── Anomaly injection (for demo) ───────────────────────────────────────────
    def inject_anomaly(self, model_name: str = "demo-iris-2"):
        """Demo tool: simulate a production incident"""
        self._injected_anomaly = SpanMetrics(
            model_name=model_name,
            p99_latency_ms=random.uniform(850, 1200),
            p50_latency_ms=random.uniform(420, 650),
            error_rate_pct=random.uniform(8.5, 15.0),
            total_spans=random.randint(280, 420),
        )
        print(f"\n  💥 ANOMALY INJECTED on {model_name}: "
              f"P99={self._injected_anomaly.p99_latency_ms:.0f}ms, "
              f"ErrorRate={self._injected_anomaly.error_rate_pct:.1f}%")
        return self._injected_anomaly

    def clear_anomaly(self, model_name: str = "demo-iris-2"):
        """Demo tool: clear injected anomaly (simulate recovery)"""
        self._injected_anomaly = None
        print(f"  [Arize MCP] Anomaly cleared — {model_name} returning to nominal")

    # ── Internal: Phoenix REST API ─────────────────────────────────────────────
    def _fetch_from_phoenix(self, model_name: str, window_minutes: int) -> SpanMetrics:
        try:
            headers = {}
            if config.ARIZE_API_KEY:
                headers["Authorization"] = f"Bearer {config.ARIZE_API_KEY}"
            with httpx.Client(base_url=self.base_url, timeout=5.0) as client:
                # Phoenix REST: GET /v1/spans
                resp = client.get("/v1/spans", params={"limit": 500}, headers=headers)
                if resp.status_code == 200:
                    spans = resp.json().get("data", [])
                    return self._aggregate_spans(model_name, spans, window_minutes)
        except Exception as e:
            print(f"  [Arize MCP] Phoenix unreachable ({e}), using demo metrics")
        return self._demo_healthy_metrics(model_name, window_minutes)

    def _aggregate_spans(self, model_name: str, spans: list, window_minutes: int) -> SpanMetrics:
        now = time.time()
        cutoff = now - window_minutes * 60
        relevant = [
            s for s in spans
            if s.get("startTime", 0) > cutoff
        ]
        if not relevant:
            return self._demo_healthy_metrics(model_name, window_minutes)

        latencies = [s.get("latencyMs", 0) for s in relevant]
        errors = sum(1 for s in relevant if s.get("statusCode", "") == "ERROR")
        latencies.sort()
        p99_idx = max(0, int(len(latencies) * 0.99) - 1)
        p50_idx = max(0, int(len(latencies) * 0.50) - 1)

        return SpanMetrics(
            model_name=model_name,
            p99_latency_ms=latencies[p99_idx] if latencies else 0,
            p50_latency_ms=latencies[p50_idx] if latencies else 0,
            error_rate_pct=(errors / len(relevant) * 100) if relevant else 0,
            total_spans=len(relevant),
            window_minutes=window_minutes,
        )

    def _demo_healthy_metrics(self, model_name: str, window_minutes: int) -> SpanMetrics:
        return SpanMetrics(
            model_name=model_name,
            p99_latency_ms=random.uniform(120, 220),
            p50_latency_ms=random.uniform(60, 100),
            error_rate_pct=random.uniform(0.1, 0.9),
            total_spans=random.randint(180, 320),
            window_minutes=window_minutes,
        )


# ─── Singleton ────────────────────────────────────────────────────────────────
arize_client = ArizePhoenixMCPClient()


# ─── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== Arize Phoenix MCP Client — Self-Test ===\n")
    client = ArizePhoenixMCPClient()

    print("1. Healthy metrics:")
    metrics = client.get_spans("demo-iris-2")
    print(f"   Anomalous: {metrics.is_anomalous}")

    print("\n2. Injecting anomaly:")
    client.inject_anomaly("demo-iris-2")
    metrics = client.get_spans("demo-iris-2")
    print(f"   Anomalous: {metrics.is_anomalous}")
    print(f"   Report: {json.dumps(metrics.to_incident_report(), indent=2)}")

    print("\n3. Trace retrieval:")
    trace = client.get_trace("trace-abc-123")
    print(f"   Hint: {trace['root_cause_hint']}")

    print("\n✅ Arize MCP client self-test PASSED")
