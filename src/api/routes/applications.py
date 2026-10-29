from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import hashlib
import secrets

from src.core.auth import AuthManager, require_scopes

router = APIRouter(prefix="/applications", tags=["applications"])

state: Dict[str, Any] = {}

def set_state(s: Dict[str, Any]):
    global state
    state = s

# Models
class ApplicationCreate(BaseModel):
    id: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    name: str
    description: Optional[str] = None

class ApplicationResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    created_at: str

class CollectionCreate(BaseModel):
    id: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    name: str
    description: Optional[str] = None
    embedding_model: Optional[str] = "BAAI/bge-small-en-v1.5"
    chunk_strategy: Optional[str] = "recursive"
    chunk_size: Optional[int] = 500
    chunk_overlap: Optional[int] = 50

class CollectionResponse(BaseModel):
    id: str
    application_id: str
    name: str
    embedding_model: str
    embedding_dim: int
    chunk_strategy: str
    chunk_size: int
    chunk_overlap: int
    created_at: str

class APIKeyCreate(BaseModel):
    name: str
    scopes: Optional[List[str]] = None

class APIKeyResponse(BaseModel):
    key: str
    key_id: str
    name: str
    application_id: str
    scopes: List[str]
    created_at: str

class APIKeyListResponse(BaseModel):
    key_id: str
    name: str
    application_id: str
    scopes: List[str]
    created_at: str
    last_used_at: Optional[str]
    revoked: bool

# Helpers
def get_sqlite():
    return state["sqlite"]

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_application(
    app: ApplicationCreate,
):
    """Register a new application. Public endpoint (no auth required for initial setup)."""
    sqlite = state["sqlite"]
    
    # Check if exists
    existing = sqlite.get_application(app.id)
    if existing:
        raise HTTPException(status_code=409, detail="Application already exists")
    
    result = sqlite.register_application(app.id, app.name, app.description)
    
    return ApplicationResponse(
        id=result["id"],
        name=result["name"],
        description=result["description"],
        created_at=result["created_at"],
    )

@router.get("/{app_id}")
async def get_application(
    app_id: str,
    key_info: Dict[str, Any] = Depends(require_scopes("read")),
):
    """Get application details. Requires read scope."""
    sqlite = state["sqlite"]
    app = sqlite.get_application(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return ApplicationResponse(**app)

@router.get("")
async def list_applications(
    key_info: Dict[str, Any] = Depends(require_scopes("read")),
):
    """List all applications. Requires read scope."""
    sqlite = state["sqlite"]
    with sqlite.get_connection() as conn:
        rows = conn.execute("SELECT * FROM applications ORDER BY created_at DESC").fetchall()
    return [ApplicationResponse(**dict(row)) for row in rows]

# API Key management endpoints
@router.post("/{app_id}/keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    app_id: str,
    key_req: APIKeyCreate,
    key_info: Dict[str, Any] = Depends(require_scopes("admin")),
):
    """Create a new API key for an application. Requires admin scope."""
    auth_manager = state["auth"]
    key, key_info = auth_manager.create_key(
        application_id=app_id,
        name=key_req.name,
        scopes=key_req.scopes,
    )
    return APIKeyResponse(
        key=key,
        key_id=key_info["key_id"],
        name=key_info["name"],
        application_id=key_info["application_id"],
        scopes=key_info["scopes"],
        created_at=key_info["created_at"],
    )

@router.get("/{app_id}/keys")
async def list_api_keys(
    app_id: str,
    key_info: Dict[str, Any] = Depends(require_scopes("admin")),
):
    """List all API keys for an application. Requires admin scope."""
    auth_manager = state["auth"]
    keys = auth_manager.list_keys(app_id)
    return [APIKeyListResponse(**k) for k in keys]

@router.delete("/{app_id}/keys/{key_id}")
async def revoke_api_key(
    app_id: str,
    key_id: str,
    key_info: Dict[str, Any] = Depends(require_scopes("admin")),
):
    """Revoke an API key. Requires admin scope."""
    auth_manager = state["auth"]
    success = auth_manager.revoke_key(key_id, app_id)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"success": True, "message": "API key revoked"}

@router.post("/{app_id}/collections", status_code=status.HTTP_201_CREATED)
async def create_collection(
    app_id: str,
    collection: CollectionCreate,
    key_info: Dict[str, Any] = Depends(require_scopes("write")),
):
    """Create a new collection within an application. Requires write scope."""
    sqlite = state["sqlite"]
    
    # Verify application exists
    if not sqlite.get_application(app_id):
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Get the actual embedding dimension from the provider
    embeddings = state["embeddings"]
    embedding_dim = embeddings.dimension
    
    result = sqlite.create_collection(
        app_id=app_id,
        collection_id=collection.id,
        name=collection.name,
        embedding_model=collection.embedding_model,
        embedding_dim=embedding_dim,
        chunk_strategy=collection.chunk_strategy,
        chunk_size=collection.chunk_size,
        chunk_overlap=collection.chunk_overlap,
        description=collection.description,
    )
    
    return CollectionResponse(**result)

@router.get("/{app_id}/collections/{collection_id}")
async def get_collection(
    app_id: str,
    collection_id: str,
    key_info: Dict[str, Any] = Depends(require_scopes("read")),
):
    """Get collection details. Requires read scope."""
    sqlite = state["sqlite"]
    coll = sqlite.get_collection(app_id, collection_id)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    return CollectionResponse(**coll)

@router.get("/{app_id}/collections")
async def list_collections(
    app_id: str,
    key_info: Dict[str, Any] = Depends(require_scopes("read")),
):
    """List all collections for an application. Requires read scope."""
    sqlite = state["sqlite"]
    with sqlite.get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM collections WHERE application_id = ? ORDER BY created_at DESC",
            (app_id,)
        ).fetchall()
    return [CollectionResponse(**dict(row)) for row in rows]