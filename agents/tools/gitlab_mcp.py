"""
NeuroScale 2.0 — GitLab MCP Client
Operator Agent tool: creates branches, commits YAML fixes, opens Merge Requests.
Implements GitLab REST API v4 (mirrors @zereight/mcp-gitlab MCP server tools).
In demo mode: simulates MR creation with realistic output.
"""
from __future__ import annotations
import json, time, base64, random, string
from dataclasses import dataclass
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
class MergeRequest:
    iid: int
    title: str
    description: str
    branch: str
    web_url: str
    state: str = "opened"
    created_at: str = ""

    def __str__(self):
        return f"MR !{self.iid}: {self.title} [{self.state}]\n  Branch: {self.branch}\n  URL: {self.web_url}"


# ─── MCP Client ───────────────────────────────────────────────────────────────

class GitLabMCPClient:
    """
    MCP client wrapping GitLab REST API v4.
    Mirrors the tools exposed by @zereight/mcp-gitlab:
      - mcp_gitlab_create_branch
      - mcp_gitlab_create_file / update_file
      - mcp_gitlab_create_merge_request
      - mcp_gitlab_get_file
    """

    def __init__(self):
        self.base_url = config.GITLAB_BASE_URL.rstrip("/")
        self.token = config.GITLAB_TOKEN
        self.project_id = config.GITLAB_PROJECT_ID
        self._demo_mode = config.DEMO_MODE or not config.gitlab_configured()
        self._demo_mr_counter = random.randint(40, 60)

    # ── MCP Tool: create_branch ────────────────────────────────────────────────
    def create_branch(self, branch_name: str, ref: str = None) -> dict:
        """MCP tool: mcp_gitlab_create_branch"""
        ref = ref or config.GITLAB_DEFAULT_BRANCH
        print(f"  [GitLab MCP] Creating branch: {branch_name} (from {ref})")

        if self._demo_mode:
            result = {"name": branch_name, "commit": {"id": f"demo_{branch_name[:8]}"}, "web_url": f"{self.base_url}/neuroscale-platform/-/tree/{branch_name}"}
            print(f"  [GitLab MCP] ✓ Branch created: {result['web_url']}")
            return result

        resp = self._api("POST", f"/projects/{self.project_id}/repository/branches",
                         json={"branch": branch_name, "ref": ref})
        print(f"  [GitLab MCP] ✓ Branch created: {resp.get('web_url', branch_name)}")
        return resp

    # ── MCP Tool: get_file ─────────────────────────────────────────────────────
    def get_file(self, file_path: str, ref: str = None) -> str:
        """MCP tool: mcp_gitlab_get_file — returns decoded file content"""
        ref = ref or config.GITLAB_DEFAULT_BRANCH
        print(f"  [GitLab MCP] Reading file: {file_path} @ {ref}")

        if self._demo_mode:
            return self._demo_file_content(file_path)

        resp = self._api("GET", f"/projects/{self.project_id}/repository/files/{file_path.replace('/', '%2F')}",
                         params={"ref": ref})
        content = base64.b64decode(resp["content"]).decode("utf-8")
        return content

    # ── MCP Tool: update_file ──────────────────────────────────────────────────
    def commit_file(self, branch: str, file_path: str, content: str, commit_message: str) -> dict:
        """MCP tool: mcp_gitlab_update_file (or create_file if new)"""
        print(f"  [GitLab MCP] Committing {file_path} → {branch}")
        print(f"  [GitLab MCP] Message: {commit_message}")

        if self._demo_mode:
            result = {"file_path": file_path, "branch": branch, "commit_id": f"demo_{branch[:8]}abc"}
            print(f"  [GitLab MCP] ✓ File committed: {file_path}")
            return result

        # Try update first, fall back to create
        payload = {
            "branch": branch,
            "content": content,
            "commit_message": commit_message,
            "encoding": "text",
        }
        try:
            resp = self._api("PUT",
                f"/projects/{self.project_id}/repository/files/{file_path.replace('/', '%2F')}",
                json=payload)
        except Exception:
            resp = self._api("POST",
                f"/projects/{self.project_id}/repository/files/{file_path.replace('/', '%2F')}",
                json=payload)
        print(f"  [GitLab MCP] ✓ Committed: {file_path}")
        return resp

    # ── MCP Tool: create_merge_request ────────────────────────────────────────
    def create_merge_request(
        self,
        title: str,
        description: str,
        source_branch: str,
        target_branch: str = None,
        labels: list[str] = None,
    ) -> MergeRequest:
        """MCP tool: mcp_gitlab_create_merge_request"""
        target_branch = target_branch or config.GITLAB_DEFAULT_BRANCH
        labels = labels or ["neuroscale-agent", "autonomous-remediation", "sre"]
        print(f"  [GitLab MCP] Creating Merge Request: '{title}'")
        print(f"  [GitLab MCP] {source_branch} → {target_branch}")

        if self._demo_mode:
            self._demo_mr_counter += 1
            iid = self._demo_mr_counter
            web_url = f"{self.base_url}/neuroscale-platform/-/merge_requests/{iid}"
            mr = MergeRequest(
                iid=iid,
                title=title,
                description=description,
                branch=source_branch,
                web_url=web_url,
                state="opened",
                created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
            print(f"\n  ╔══════════════════════════════════════════════════════╗")
            print(f"  ║  🤖 AGENT CREATED MERGE REQUEST                      ║")
            print(f"  ║  MR !{iid:<6} {title[:42]:<42}  ║")
            print(f"  ║  URL: {web_url:<46}  ║")
            print(f"  ╚══════════════════════════════════════════════════════╝\n")
            return mr

        payload = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": description,
            "labels": ",".join(labels),
            "remove_source_branch": True,
        }
        resp = self._api("POST", f"/projects/{self.project_id}/merge_requests", json=payload)
        mr = MergeRequest(
            iid=resp["iid"],
            title=resp["title"],
            description=resp.get("description", ""),
            branch=source_branch,
            web_url=resp["web_url"],
            state=resp["state"],
            created_at=resp.get("created_at", ""),
        )
        print(f"\n  🎯 MR Created: {mr.web_url}")
        return mr

    # ── Internal: HTTP helper ──────────────────────────────────────────────────
    def _api(self, method: str, path: str, **kwargs) -> dict:
        if not _HTTPX:
            raise RuntimeError("httpx not installed — run: pip install httpx")
        url = f"{self.base_url}/api/v4{path}"
        headers = {"PRIVATE-TOKEN": self.token, "Content-Type": "application/json"}
        with httpx.Client(timeout=15.0) as client:
            resp = client.request(method, url, headers=headers, **kwargs)
        if resp.status_code >= 400:
            raise RuntimeError(f"GitLab API error {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    # ── Demo helpers ───────────────────────────────────────────────────────────
    def _demo_file_content(self, file_path: str) -> str:
        if "sklearn-runtime" in file_path or "inference-service" in file_path:
            return """apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: demo-iris-2
  namespace: default
  labels:
    owner: platform-team
    cost-center: cc-demo
spec:
  predictor:
    model:
      modelFormat:
        name: sklearn
      storageUri: "gs://kfserving-examples/models/sklearn/1.0/model"
      resources:
        requests:
          cpu: 100m
          memory: 256Mi
        limits:
          cpu: 500m
          memory: 512Mi
"""
        return f"# {file_path}\n# demo content\n"


# ─── Singleton ────────────────────────────────────────────────────────────────
gitlab_client = GitLabMCPClient()


# ─── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== GitLab MCP Client — Self-Test ===\n")
    client = GitLabMCPClient()

    branch = f"agent/remediation-demo-{int(time.time())}"

    print("1. Create branch:")
    b = client.create_branch(branch)
    print(f"   OK: {b['name']}")

    print("\n2. Read file:")
    content = client.get_file("apps/demo-iris-2/inference-service.yaml")
    print(f"   Lines: {len(content.splitlines())}")

    print("\n3. Commit file:")
    fixed = content.replace("memory: 256Mi", "memory: 512Mi")
    commit = client.commit_file(branch, "apps/demo-iris-2/inference-service.yaml",
                                fixed, "fix(agent): increase memory limits for demo-iris-2")
    print(f"   OK: {commit['file_path']}")

    print("\n4. Create MR:")
    mr = client.create_merge_request(
        title="fix(agent): Autonomous remediation — CPU throttling on demo-iris-2",
        description="Agent detected P99 latency breach. Applying memory limit fix per Runbook #7.",
        source_branch=branch,
    )
    print(f"   {mr}")

    print("\n✅ GitLab MCP client self-test PASSED")
