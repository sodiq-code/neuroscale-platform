"""
NeuroScale 2.0 — A2A Orchestrator
Drives the full agent pipeline: Watcher → Diagnostician → Operator

Modes:
  run_once()       — single pipeline pass (demo / CI)
  run_continuous() — infinite loop (production)

Usage:
  python3 agents/orchestrator.py             # run_once demo
  python3 agents/orchestrator.py --watch     # continuous loop
  python3 agents/orchestrator.py --self-test # run self-test
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
AGENTS_DIR = Path(__file__).parent
REPO_ROOT = AGENTS_DIR.parent
import sys
sys.path.insert(0, str(REPO_ROOT))

import agents.config as cfg
from agents.watcher import WatcherAgent
from agents.diagnostician import DiagnosticianAgent
from agents.operator_agent import OperatorAgent

logger = logging.getLogger("neuroscale.orchestrator")


# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------
C = {
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "CYAN": "\033[96m",
    "RED": "\033[91m",
    "MAGENTA": "\033[95m",
    "BLUE": "\033[94m",
    "DIM": "\033[2m",
}

def _c(color: str, text: str) -> str:
    return f"{C.get(color, '')}{text}{C['RESET']}"

def _banner(title: str, color: str = "CYAN"):
    width = 65
    bar = "═" * width
    print(f"\n{_c(color, bar)}")
    print(f"{_c(color, '  ' + title)}")
    print(f"{_c(color, bar)}")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class NeuroScaleOrchestrator:
    """
    Top-level A2A orchestrator.

    Each pipeline run:
      1. Watcher   — detects anomalies from Arize Phoenix metrics
      2. Diagnostician — root-causes each anomaly, builds remediation plan
      3. Operator  — creates GitLab branch, commits fix, opens MR, sends HITL

    All three agents are stateless; state lives in the pipeline_context dict
    passed between them.
    """

    def __init__(self):
        self.watcher = WatcherAgent()
        self.diagnostician = DiagnosticianAgent()
        self.operator = OperatorAgent()
        self._run_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_once(self, inject_anomaly: bool = False) -> dict:
        """Single pipeline pass. Returns full context dict."""
        self._run_count += 1
        run_id = f"RUN-{self._run_count:04d}-{int(time.time())}"
        context: dict[str, Any] = {
            "run_id": run_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "inject_anomaly": inject_anomaly,
            "anomalies": [],
            "diagnoses": [],
            "operations": [],
            "errors": [],
        }

        _banner(f"NeuroScale 2.0  |  A2A Pipeline  |  {run_id}", "CYAN")
        print(_c("DIM", f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"))
        print()

        # ── Phase 1: WATCHER ──────────────────────────────────────────
        self._phase_header("1", "WATCHER AGENT", "Polling Arize Phoenix metrics …")
        anomalies = self._run_watcher(context, inject_anomaly)

        if not anomalies:
            print(_c("GREEN", "  ✅  No anomalies detected — system nominal\n"))
            context["status"] = "NOMINAL"
            context["ended_at"] = datetime.now(timezone.utc).isoformat()
            return context

        print(_c("YELLOW", f"  ⚠️   {len(anomalies)} anomaly(ies) detected — escalating …\n"))

        # ── Phase 2: DIAGNOSTICIAN ────────────────────────────────────
        self._phase_header("2", "DIAGNOSTICIAN AGENT", "Root-causing anomalies …")
        diagnoses = self._run_diagnostician(context, anomalies)

        # ── Phase 3: OPERATOR ─────────────────────────────────────────
        self._phase_header("3", "OPERATOR AGENT", "Executing remediation …")
        operations = self._run_operator(context, diagnoses)

        # ── Summary ───────────────────────────────────────────────────
        context["status"] = "REMEDIATED" if operations else "DIAGNOSED_NO_ACTION"
        context["ended_at"] = datetime.now(timezone.utc).isoformat()
        self._print_summary(context)
        return context

    def run_continuous(self, interval_seconds: int = 30, inject_on_first: bool = True):
        """Continuous watch loop — runs until interrupted."""
        _banner("NeuroScale 2.0  |  Continuous Watch Mode", "MAGENTA")
        print(f"  Poll interval : {interval_seconds}s")
        print(f"  Press Ctrl+C to stop\n")

        iteration = 0
        try:
            while True:
                inject = inject_on_first and iteration == 0
                self.run_once(inject_anomaly=inject)
                iteration += 1
                print(_c("DIM", f"  Sleeping {interval_seconds}s until next poll …\n"))
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print(_c("YELLOW", "\n  🛑  Watch mode stopped by user\n"))

    # ------------------------------------------------------------------
    # Phase runners
    # ------------------------------------------------------------------

    def _run_watcher(self, context: dict, inject_anomaly: bool) -> list:
        try:
            if inject_anomaly:
                logger.info("  Injecting demo anomaly …")
                # Inject into watcher's own arize client instance
                if hasattr(self.watcher, 'arize'):
                    self.watcher.arize.inject_anomaly()
                elif hasattr(self.watcher, 'arize_client'):
                    self.watcher.arize_client.inject_anomaly()

            incident = self.watcher.run_poll()
            anomalies = []

            if incident:
                # Watcher returns incident with model_name in root dict
                model_name = incident.get("model_name") or incident.get("model_id", "demo-iris-2")
                # Normalise watcher incident → anomaly dict expected by Diagnostician
                raw_metrics = incident.get("metrics", {})
                hypo = incident.get("agent_hypothesis", incident.get("hypothesis", ""))
                anomaly = {
                    "service": model_name,
                    "model_id": model_name,
                    "model_name": model_name,   # diagnostician key
                    "incident_id": incident.get("incident_id", f"INC-{int(time.time())}"),
                    "detected_at": incident.get("detected_at", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
                    "severity": incident.get("severity", "CRITICAL"),
                    "metric": "latency_p99_ms",
                    "value": raw_metrics.get("p99_latency_ms", 0),
                    "threshold": 500.0,
                    "hypothesis": hypo,
                    "agent_hypothesis": hypo,  # diagnostician uses this key
                    "metrics": raw_metrics,     # diagnostician uses this sub-dict
                    "raw": incident,
                }
                anomalies.append(anomaly)

            context["anomalies"] = anomalies
            context["watcher_result"] = incident

            for a in anomalies:
                svc = a.get("service", "unknown")
                metric = a.get("metric", "unknown")
                val = a.get("value", "?")
                thr = a.get("threshold", "?")
                print(f"  {_c('RED', '🚨')} {_c('BOLD', svc)} | {metric} = {_c('RED', str(val))} (threshold: {thr})")

            return anomalies

        except Exception as exc:
            logger.error(f"Watcher error: {exc}", exc_info=True)
            context["errors"].append({"phase": "watcher", "error": str(exc)})
            return []

    def _run_diagnostician(self, context: dict, anomalies: list) -> list:
        diagnoses = []
        for anomaly in anomalies:
            try:
                raw_plan = self.diagnostician.diagnose(anomaly)

                # Normalise diagnostician plan → operator remediation_plan schema
                root_cause = raw_plan.get("root_cause", {})
                actions = raw_plan.get("actions", [])
                steps = [a.get("description", str(a)) for a in actions if isinstance(a, dict)]

                # Extract YAML patch from first action that has one
                yaml_patch = None
                yaml_patch_path = None
                for a in actions:
                    if isinstance(a, dict) and a.get("yaml_patch"):
                        yaml_patch = a["yaml_patch"]
                        yaml_patch_path = a.get("file")
                        break

                # Convert string confidence ("HIGH"/"MEDIUM"/"LOW") to float
                raw_confidence = root_cause.get("confidence", 0.80)
                if isinstance(raw_confidence, str):
                    raw_confidence = {"HIGH": 0.90, "MEDIUM": 0.75, "LOW": 0.50}.get(raw_confidence.upper(), 0.75)

                remediation_plan = {
                    "incident_id": raw_plan.get("incident_id", anomaly.get("incident_id", f"INC-{int(time.time())}")),
                    "anomaly": anomaly,
                    "diagnosis": root_cause.get("description", raw_plan.get("plan_id", "See runbook")),
                    "recommended_runbook": root_cause.get("runbook_ref", "RB-001"),
                    "steps": steps,
                    "yaml_patch": yaml_patch,
                    "yaml_patch_path": yaml_patch_path,
                    "confidence": raw_confidence,
                    "requires_human_approval": raw_plan.get("hitl_required", True),
                    "_raw": raw_plan,
                }

                diagnoses.append(remediation_plan)
                context["diagnoses"].append(remediation_plan)

                svc = anomaly.get("service") or anomaly.get("model_id", "unknown")
                runbook = remediation_plan["recommended_runbook"]
                confidence = remediation_plan["confidence"]
                diagnosis_text = remediation_plan["diagnosis"][:80]

                print(f"  {_c('BLUE', '🔍')} {_c('BOLD', svc)}")
                print(f"     Runbook    : {_c('CYAN', runbook)}")
                print(f"     Confidence : {_c('GREEN' if confidence > 0.8 else 'YELLOW', f'{confidence:.1%}')}")
                print(f"     Diagnosis  : {diagnosis_text} …")
                print()

            except Exception as exc:
                logger.error(f"Diagnostician error for {anomaly}: {exc}", exc_info=True)
                context["errors"].append({"phase": "diagnostician", "anomaly": anomaly, "error": str(exc)})

        return diagnoses

    def _run_operator(self, context: dict, diagnoses: list) -> list:
        operations = []
        for plan in diagnoses:
            try:
                report = self.operator.execute(plan)
                operations.append(report)
                context["operations"].append(report)

                mr_url = report.get("mr_url", "#")
                status = report.get("status", "UNKNOWN")
                incident = report.get("incident_id", "?")

                status_color = "GREEN" if status == "AUTO_MERGED" else "YELLOW"
                print(f"  {_c('MAGENTA', '⚙️')}  {_c('BOLD', incident)}")
                print(f"     Status : {_c(status_color, status)}")
                print(f"     MR     : {_c('CYAN', mr_url)}")
                print()

            except Exception as exc:
                logger.error(f"Operator error for plan {plan}: {exc}", exc_info=True)
                context["errors"].append({"phase": "operator", "plan": plan, "error": str(exc)})

        return operations

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def _phase_header(self, num: str, name: str, subtitle: str):
        print(f"{_c('BOLD', f'  Phase {num}: {name}')}")
        print(f"  {_c('DIM', subtitle)}")
        print()

    def _print_summary(self, context: dict):
        ops = context.get("operations", [])
        errors = context.get("errors", [])
        anomaly_count = len(context.get("anomalies", []))
        mr_urls = [op.get("mr_url", "") for op in ops]

        _banner("PIPELINE SUMMARY", "GREEN" if not errors else "YELLOW")
        print(f"  Run ID      : {context['run_id']}")
        print(f"  Status      : {_c('GREEN' if not errors else 'YELLOW', context.get('status', 'UNKNOWN'))}")
        print(f"  Anomalies   : {anomaly_count}")
        print(f"  Diagnosed   : {len(context.get('diagnoses', []))}")
        print(f"  MRs Opened  : {len(ops)}")
        if mr_urls:
            for url in mr_urls:
                print(f"  MR URL      : {_c('CYAN', url)}")
        if errors:
            print(f"  Errors      : {_c('RED', str(len(errors)))}")
        print()


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test():
    logging.basicConfig(level=logging.WARNING)
    print("\n🧪 Orchestrator self-test …")

    orch = NeuroScaleOrchestrator()
    ctx = orch.run_once(inject_anomaly=True)

    assert ctx.get("run_id"), "Missing run_id"
    assert ctx.get("started_at"), "Missing started_at"
    assert ctx.get("status") in ("REMEDIATED", "NOMINAL", "DIAGNOSED_NO_ACTION"), f"Bad status: {ctx.get('status')}"

    if ctx.get("status") == "REMEDIATED":
        assert len(ctx["operations"]) > 0, "Status REMEDIATED but no operations"

    print(f"✅ PASSED — Orchestrator self-test | status={ctx['status']}")
    return ctx


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NeuroScale 2.0 A2A Orchestrator")
    parser.add_argument("--watch", action="store_true", help="Run continuous watch loop")
    parser.add_argument("--interval", type=int, default=30, help="Poll interval in seconds (watch mode)")
    parser.add_argument("--inject", action="store_true", default=True, help="Inject anomaly on first run")
    parser.add_argument("--self-test", action="store_true", dest="self_test", help="Run self-test and exit")
    parser.add_argument("--quiet", action="store_true", help="Suppress debug logs")
    args = parser.parse_args()

    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s  %(name)s  %(message)s")

    if args.self_test:
        _self_test()
    elif args.watch:
        orch = NeuroScaleOrchestrator()
        orch.run_continuous(interval_seconds=args.interval, inject_on_first=args.inject)
    else:
        orch = NeuroScaleOrchestrator()
        orch.run_once(inject_anomaly=args.inject)
