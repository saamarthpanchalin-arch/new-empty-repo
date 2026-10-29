"""
Campus Issues — FastAPI application entry point.
Reuses the existing Local RAG infrastructure for search and duplicate detection.
"""
import logging
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

# Make the existing local-rag/src importable so we reuse its core modules
# __file__ = .../local-rag/campus-issues/src/api/main.py
# 3 levels up reaches .../local-rag (api -> src -> campus-issues -> local-rag)
_LOCALRAG = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _LOCALRAG not in sys.path:
    sys.path.insert(0, _LOCALRAG)

from src.core.sqlite_store import SQLiteStore
from src.core.qdrant_store import QdrantStore
from src.core.embedding import EmbeddingProvider
from src.core.ingestion import IngestionService
from src.core.retrieval import HybridRetrievalService
from app.core.campus_auth import CampusAuthManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

state = {}

SECRET_KEY = os.getenv("CAMPUS_SECRET_KEY", "dev-secret-change-in-production")
CAMPUS_APP_ID = "campus-issues"
CAMPUS_COLLECTION = "tickets"

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Campus Issues Service...")

    # SQLite (shared metadata DB)
    state["sqlite"] = SQLiteStore("data/metadata.db")
    logger.info("SQLite initialized")

    # Qdrant
    state["qdrant"] = QdrantStore(host="localhost", port=6333, use_memory=False)
    logger.info("Qdrant client initialized")

    # Embeddings
    state["embeddings"] = EmbeddingProvider(model_name="BAAI/bge-small-en-v1.5", device="cpu")
    logger.info(f"Embeddings initialized (dim={state['embeddings'].dimension})")

    # Auth
    state["campus_auth"] = CampusAuthManager(state["sqlite"], SECRET_KEY)
    logger.info("Campus Auth manager initialized")

    # Ensure RAG application and collection exist
    state["qdrant"].create_collection(f"{CAMPUS_APP_ID}_{CAMPUS_COLLECTION}", vector_size=state["embeddings"].dimension)
    # Register the application if it doesn't exist
    if not state["sqlite"].get_application(CAMPUS_APP_ID):
        state["sqlite"].register_application(CAMPUS_APP_ID, "Campus Issues", "Campus issue tracking system")
    state["sqlite"].create_collection(
        app_id=CAMPUS_APP_ID,
        collection_id=CAMPUS_COLLECTION,
        name="Campus Issue Tickets",
        embedding_model="BAAI/bge-small-en-v1.5",
        embedding_dim=state["embeddings"].dimension,
        description="Ticket descriptions for duplicate detection"
    )

    # Ingestion
    state["ingestion"] = IngestionService(
        sqlite_store=state["sqlite"],
        qdrant_store=state["qdrant"],
        embedding_provider=state["embeddings"],
    )
    logger.info("Ingestion service initialized")

    # Retrieval
    state["retrieval"] = HybridRetrievalService(
        sqlite_store=state["sqlite"],
        qdrant_store=state["qdrant"],
        embedding_provider=state["embeddings"],
    )
    logger.info("Retrieval service initialized")

    # Seed sample data if empty
    seed_sample_data(state["sqlite"], state["campus_auth"])

    # Inject state into route module
    from app.routes.campus_issues import set_state
    set_state(state)

    logger.info("Campus Issues Service ready")
    yield

    logger.info("Shutting down Campus Issues Service...")

app = FastAPI(title="Campus Issues", version="1.0.0", lifespan=lifespan)

CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8001,http://localhost:8080").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

# Include routes
from app.routes.campus_issues import router
app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "Campus Issues"}

@app.get("/health/ready")
async def ready():
    return {
        "status": "ready",
        "checks": {
            "sqlite": "ok" if state.get("sqlite") else "down",
            "qdrant": "ok" if state.get("qdrant") else "down",
            "embeddings": "ok" if state.get("embeddings") else "down",
        }
    }

def seed_sample_data(sqlite: SQLiteStore, auth: CampusAuthManager):
    """Seed synthetic sample users and buildings if the database is empty."""
    try:
        existing = sqlite.get_all_tickets(limit=1)
        if existing:
            return  # Already seeded

        # Create sample students
        students = [
            ("alice_smith", "alice@example.com", "student123", "Alice Smith"),
            ("bob_jones", "bob@example.com", "student123", "Bob Jones"),
        ]
        for username, email, password, name in students:
            auth.register_user(username, email, password, "student")

        # Create sample staff
        staff = [
            ("maintenance", "maintenance@campus.local", "staff123", "Maintenance Team"),
            ("facilities", "facilities@campus.local", "staff123", "Facilities Dept"),
        ]
        for username, email, password, name in staff:
            auth.register_user(username, email, password, "staff")

        # Create admin
        auth.register_user("admin", "admin@campus.local", "admin123", "Administrator")

        logger.info("Sample users seeded (synthetic, not real identities)")
    except Exception as e:
        logger.warning(f"Seed data skipped: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)