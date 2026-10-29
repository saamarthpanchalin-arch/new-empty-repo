from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from src.core.auth import require_scopes

router = APIRouter(prefix="/generate", tags=["generation"])

state: Dict[str, Any] = {}

def set_state(s: Dict[str, Any]):
    global state
    state = s

# Models
class AskRequest(BaseModel):
    query: str
    app_id: str
    collection_id: str
    top_k: int = Field(default=5, ge=1, le=20)
    filter_conditions: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    max_tokens: int = Field(default=512, ge=64, le=2048)
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)

class AskResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    model: str
    retrieval_results_count: int
    grounded: bool

class ModelsResponse(BaseModel):
    available: List[str]
    default: Optional[str]

def get_generation():
    return state["generation"]

def get_retrieval():
    return state["retrieval"]

async def get_ask_request(request: Request) -> AskRequest:
    """Extract and validate ask request from body."""
    body = await request.json()
    return AskRequest(**body)

@router.post("/ask", response_model=AskResponse)
async def ask(
    ask_request: AskRequest = Depends(get_ask_request),
    key_info: Dict[str, Any] = Depends(require_scopes("read")),
):
    """Grounded question answering with retrieval. Requires read scope."""
    retrieval = get_retrieval()
    generation = get_generation()
    
    # Get context from retrieval
    context, sources = retrieval.get_context(
        app_id=ask_request.app_id,
        collection_id=ask_request.collection_id,
        query=ask_request.query,
        top_k=ask_request.top_k,
        filter_conditions=ask_request.filter_conditions,
    )
    
    # Select adapter
    adapter = generation.get_adapter(ask_request.model)
    
    try:
        result = adapter.generate(
            query=ask_request.query,
            context=context,
            max_tokens=ask_request.max_tokens,
            temperature=ask_request.temperature,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Generation failed: {str(e)}")
    
    return AskResponse(
        answer=result.answer,
        sources=[
            {
                "chunk_id": s.chunk_id,
                "document_id": s.document_id,
                "source_uri": s.source_uri,
                "chunk_index": s.chunk_index,
                "score": s.score,
            }
            for s in sources
        ],
        model=result.model,
        retrieval_results_count=len(sources),
        grounded=result.grounded,
    )

@router.get("/models", response_model=ModelsResponse)
async def list_models(
    key_info: Dict[str, Any] = Depends(require_scopes("read")),
):
    """List available generation models. Requires read scope."""
    generation = get_generation()
    return ModelsResponse(
        available=generation.list_adapters(),
        default=generation.default_adapter,
    )