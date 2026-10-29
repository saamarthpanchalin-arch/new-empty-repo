from fastapi import APIRouter, HTTPException
from typing import Dict, Any

router = APIRouter(prefix="/health", tags=["health"])

# This will be injected by main app
state: Dict[str, Any] = {}

def set_state(s: Dict[str, Any]):
    global state
    state = s

@router.get("/")
async def health_check():
    """Basic health check."""
    return {"status": "healthy", "service": "local-rag"}

@router.get("/ready")
async def readiness_check():
    """Readiness check - verifies dependencies."""
    checks = {}
    
    # Check SQLite
    try:
        conn = state["sqlite"].get_connection()
        conn.execute("SELECT 1")
        checks["sqlite"] = "ok"
    except Exception as e:
        checks["sqlite"] = f"error: {e}"
    
    # Check Qdrant
    try:
        state["qdrant"].client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {e}"
    
    # Check embedding provider
    try:
        _ = state["embeddings"].encode(["test"])
        checks["embeddings"] = "ok"
    except Exception as e:
        checks["embeddings"] = f"error: {e}"
    
    all_ok = all(v == "ok" for v in checks.values())
    
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
    }