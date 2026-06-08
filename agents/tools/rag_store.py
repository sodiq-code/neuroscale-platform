"""
NeuroScale 2.0 — RAG / Runbook Store
Diagnostician Agent tool: semantic search over Hermes Skill Documents.
In production: Vertex AI Search datastore.
In demo mode: local TF-IDF keyword search over runbooks/ directory.
"""
from __future__ import annotations
import os, re, json
from dataclasses import dataclass
from typing import Optional
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


@dataclass
class RunbookResult:
    title: str
    file: str
    relevance_score: float
    summary: str
    key_steps: list[str]
    tags: list[str]

    def __str__(self):
        steps = "\n".join(f"     {i+1}. {s}" for i, s in enumerate(self.key_steps))
        return (
            f"  📖 Runbook: {self.title} (score={self.relevance_score:.2f})\n"
            f"     File: {self.file}\n"
            f"     Summary: {self.summary}\n"
            f"     Steps:\n{steps}"
        )


class RunbookRAGClient:
    """
    RAG client for Hermes Skill Documents.
    Production: Vertex AI Search (REST API).
    Demo: local keyword search + scoring over runbooks/ markdown files.
    """

    def __init__(self, runbooks_dir: str = None):
        self.runbooks_dir = runbooks_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "runbooks"
        )
        self._use_vertex = config.rag_configured() and not config.DEMO_MODE
        self._index: list[dict] = []
        self._load_index()

    # ── Public: semantic_search ────────────────────────────────────────────────
    def semantic_search(self, query: str, top_k: int = 3) -> list[RunbookResult]:
        """
        Search runbooks for the most relevant remediation guidance.
        Returns top_k results sorted by relevance.
        """
        print(f"  [RAG] Semantic search: '{query}'")
        if self._use_vertex:
            results = self._vertex_search(query, top_k)
        else:
            results = self._local_search(query, top_k)
        if results:
            print(f"  [RAG] Found {len(results)} relevant runbook(s):")
            for r in results:
                print(f"  [RAG]   → {r.title} (score={r.relevance_score:.2f})")
        else:
            print("  [RAG] No relevant runbooks found — agent will reason from base knowledge")
        return results

    # ── Internal: local keyword search ────────────────────────────────────────
    def _load_index(self):
        """Load all markdown runbooks into memory index."""
        runbooks_path = os.path.abspath(self.runbooks_dir)
        if not os.path.exists(runbooks_path):
            return
        for fname in os.listdir(runbooks_path):
            if fname.endswith(".md"):
                fpath = os.path.join(runbooks_path, fname)
                try:
                    with open(fpath) as f:
                        content = f.read()
                    self._index.append({
                        "file": fname,
                        "path": fpath,
                        "content": content,
                        "words": set(re.findall(r'\w+', content.lower())),
                    })
                except Exception:
                    pass

    def _local_search(self, query: str, top_k: int) -> list[RunbookResult]:
        """TF-IDF style keyword relevance scoring."""
        query_words = set(re.findall(r'\w+', query.lower()))
        scored = []
        for doc in self._index:
            overlap = len(query_words & doc["words"])
            score = overlap / max(len(query_words), 1)
            if score > 0.1:
                scored.append((score, doc))
        scored.sort(key=lambda x: -x[0])
        results = []
        for score, doc in scored[:top_k]:
            result = self._parse_runbook(doc["file"], doc["content"], score)
            results.append(result)
        return results

    def _parse_runbook(self, fname: str, content: str, score: float) -> RunbookResult:
        """Extract structured info from runbook markdown."""
        lines = content.strip().splitlines()
        title = lines[0].lstrip("#").strip() if lines else fname
        summary_lines = [l.strip() for l in lines[1:5] if l.strip() and not l.startswith("#")]
        summary = " ".join(summary_lines)[:200] if summary_lines else "See runbook for details"

        steps = []
        in_steps = False
        for line in lines:
            if re.match(r'#{1,3}\s*(steps|recovery|fix|resolution)', line, re.I):
                in_steps = True
                continue
            if in_steps and re.match(r'^#{1,3}\s', line):
                in_steps = False
            if in_steps and (line.strip().startswith("-") or re.match(r'^\d+\.', line.strip())):
                step = re.sub(r'^[-\d.]+\s*', '', line.strip())
                if step:
                    steps.append(step[:120])
        if not steps:
            for line in lines:
                if re.match(r'^\d+\.', line.strip()):
                    step = re.sub(r'^\d+\.\s*', '', line.strip())
                    if step:
                        steps.append(step[:120])
        tags = [w for w in ["cpu", "memory", "latency", "kserve", "argocd", "kyverno",
                             "drift", "oom", "throttling", "rollback", "crash"]
                if w in content.lower()]

        return RunbookResult(
            title=title,
            file=fname,
            relevance_score=round(score, 3),
            summary=summary[:200],
            key_steps=steps[:5] if steps else ["Review cluster metrics", "Check pod logs", "Restart affected workload"],
            tags=tags[:6],
        )

    # ── Internal: Vertex AI Search ─────────────────────────────────────────────
    def _vertex_search(self, query: str, top_k: int) -> list[RunbookResult]:
        try:
            from google.cloud import discoveryengine_v1 as discoveryengine  # type: ignore
            client = discoveryengine.SearchServiceClient()
            request = discoveryengine.SearchRequest(
                serving_config=config.VERTEX_RAG_DATASTORE,
                query=query,
                page_size=top_k,
            )
            response = client.search(request)
            results = []
            for result in response.results:
                doc = result.document
                snippet = doc.derived_struct_data.get("snippets", [{}])[0].get("snippet", "")
                results.append(RunbookResult(
                    title=doc.derived_struct_data.get("title", doc.id),
                    file=doc.id,
                    relevance_score=0.9,
                    summary=snippet[:200],
                    key_steps=[snippet],
                    tags=[],
                ))
            return results
        except Exception as e:
            print(f"  [RAG] Vertex AI unreachable ({e}), falling back to local search")
            return self._local_search(query, top_k)


# ─── Singleton ────────────────────────────────────────────────────────────────
rag_client = RunbookRAGClient()


# ─── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== RAG Runbook Store — Self-Test ===\n")
    client = RunbookRAGClient()
    print(f"Loaded {len(client._index)} runbook(s) from {client.runbooks_dir}\n")

    queries = [
        "CPU throttling high latency sklearn model",
        "ArgoCD sync stuck Unknown state",
        "Kyverno webhook blocking admission",
        "KServe InferenceService not ready rollback",
    ]
    for q in queries:
        print(f"Query: '{q}'")
        results = client.semantic_search(q, top_k=2)
        if results:
            for r in results:
                print(r)
        else:
            print("  (no results)")
        print()
    print("✅ RAG store self-test PASSED")
