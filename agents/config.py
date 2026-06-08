"""
NeuroScale 2.0 — Agent Configuration
Central config for all environment variables with sensible defaults for demo.
"""
import os

# ─── Arize / Phoenix ──────────────────────────────────────────────────────────
ARIZE_PHOENIX_BASE_URL = os.getenv("ARIZE_PHOENIX_BASE_URL", "http://localhost:6006")
ARIZE_API_KEY          = os.getenv("ARIZE_API_KEY", "")  # optional for local Phoenix

# ─── GitLab ───────────────────────────────────────────────────────────────────
GITLAB_BASE_URL        = os.getenv("GITLAB_BASE_URL", "https://gitlab.com")
GITLAB_TOKEN           = os.getenv("GITLAB_TOKEN", "")
GITLAB_PROJECT_ID      = os.getenv("GITLAB_PROJECT_ID", "")   # numeric project ID
GITLAB_DEFAULT_BRANCH  = os.getenv("GITLAB_DEFAULT_BRANCH", "main")

# ─── Google Cloud / Vertex AI ─────────────────────────────────────────────────
GCP_PROJECT            = os.getenv("GCP_PROJECT", "")
GCP_REGION             = os.getenv("GCP_REGION", "us-central1")
VERTEX_RAG_DATASTORE   = os.getenv("VERTEX_RAG_DATASTORE", "")  # resource name

# ─── Agent behaviour ──────────────────────────────────────────────────────────
WATCHER_POLL_INTERVAL_S    = int(os.getenv("WATCHER_POLL_INTERVAL_S", "30"))
LATENCY_P99_THRESHOLD_MS   = float(os.getenv("LATENCY_P99_THRESHOLD_MS", "500"))
ERROR_RATE_THRESHOLD_PCT   = float(os.getenv("ERROR_RATE_THRESHOLD_PCT", "5.0"))

# ─── Demo mode ────────────────────────────────────────────────────────────────
DEMO_MODE          = os.getenv("DEMO_MODE", "true").lower() == "true"
RUNBOOKS_DIR       = os.getenv("RUNBOOKS_DIR", "runbooks")
WEBHOOK_URL        = os.getenv("WEBHOOK_URL", "")   # Slack / Teams / Discord

# ─── Notification ─────────────────────────────────────────────────────────────
NOTIFICATION_CHANNEL = os.getenv("NOTIFICATION_CHANNEL", "terminal")  # terminal | slack | webhook

# ─── Derived ──────────────────────────────────────────────────────────────────
def gitlab_configured() -> bool:
    return bool(GITLAB_TOKEN and GITLAB_PROJECT_ID)

def arize_configured() -> bool:
    return True  # Phoenix local always available

def rag_configured() -> bool:
    return bool(VERTEX_RAG_DATASTORE and GCP_PROJECT)
