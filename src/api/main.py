import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.sqlite_store import SQLiteStore
from src.core.qdrant_store import QdrantStore
from src.core.embedding import EmbeddingProvider
from src.core.ingestion import IngestionService
from src.core.retrieval import HybridRetrievalService
from src.core.generation import GenerationManager, GenerationAdapter, RetrievalOnlyAdapter
from src.core.auth import AuthManager, require_auth, require_scopes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global state
state = {}

# Configuration
CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
API_AUTH_ENABLED = os.getenv("API_AUTH_ENABLED", "true").lower() == "true"
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Local RAG Service...")
    
    # Initialize SQLite
    state["sqlite"] = SQLiteStore("data/metadata.db")
    logger.info("SQLite initialized")
    
    # Initialize Qdrant
    state["qdrant"] = QdrantStore(host="localhost", port=6333, use_memory=False)
    logger.info("Qdrant client initialized")
    
    # Initialize Embeddings
    state["embeddings"] = EmbeddingProvider(model_name="BAAI/bge-small-en-v1.5", device="cpu")
    logger.info(f"Embeddings initialized (dim={state['embeddings'].dimension})")
    
    # Initialize Auth Manager
    state["auth"] = AuthManager(state["sqlite"])
    logger.info("Auth manager initialized")
    
    # Initialize Ingestion
    state["ingestion"] = IngestionService(
        sqlite_store=state["sqlite"],
        qdrant_store=state["qdrant"],
        embedding_provider=state["embeddings"],
    )
    logger.info("Ingestion service initialized")
    
    # Initialize Retrieval
    state["retrieval"] = HybridRetrievalService(
        sqlite_store=state["sqlite"],
        qdrant_store=state["qdrant"],
        embedding_provider=state["embeddings"],
    )
    logger.info("Retrieval service initialized")
    
    # Initialize Generation Manager
    gen_manager = GenerationManager()
    # Register retrieval-only adapter as fallback
    gen_manager.register_adapter("retrieval-only", RetrievalOnlyAdapter(), default=True)
    state["generation"] = gen_manager
    logger.info("Generation manager initialized")
    
    # Inject state into route modules
    from src.api.routes import health, applications, ingestion, retrieval, generation, feedback
    for module in [health, applications, ingestion, retrieval, generation, feedback]:
        module.set_state(state)
    
    logger.info("Local RAG Service ready")
    yield
    
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title="Local RAG Knowledge Infrastructure",
    description="A modular, local-first Retrieval-Augmented Generation platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration - secure by default
if CORS_ALLOW_ORIGINS == ["*"] and CORS_ALLOW_CREDENTIALS:
    # Don't allow credentials with wildcard origin
    logger.warning("CORS configured with wildcard origin and credentials - this is insecure!")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOW_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOW_ORIGINS,
        allow_credentials=CORS_ALLOW_CREDENTIALS,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )

# Include routers
from src.api.routes import health, applications, ingestion, retrieval, generation, feedback

app.include_router(health.router)
app.include_router(applications.router)
app.include_router(ingestion.router)
app.include_router(retrieval.router)
app.include_router(generation.router)
app.include_router(feedback.router)

# Add auth manager to app state
@app.middleware("http")
async def add_auth_to_state(request, call_next):
    request.app.state.auth_manager = state.get("auth")
    response = await call_next(request)
    return response

@app.get("/")
async def root():
    return {
        "service": "Local RAG Knowledge Infrastructure",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }

# Public health endpoints (no auth required)
from src.api.routes import health
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)