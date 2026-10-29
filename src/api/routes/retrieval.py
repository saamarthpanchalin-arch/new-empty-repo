from fastapi import APIRouter, HTTPException, Depends, Body, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from src.core.auth import require_scopes

router = APIRouter(prefix="/search", tags=["retrieval"])

state: Dict[str, Any] = {}

def set_state(s: Dict[str, Any]):
    global state
    state = s

# Models
class SearchRequest(BaseModel):
    query: str
    app_id: str
    collection_id: str
    top_k: int = Field(default=10, ge=1, le=100)
    filter_conditions: Optional[Dict[str, Any]] = None
    use_hybrid: bool = True

class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    score: float
    rank: int
    retrieval_method: str
    payload: Dict[str, Any]
    source_uri: str
    chunk_index: int

class SearchResponse(BaseModel):
    results: List[SearchResult]

class ContextRequest(BaseModel):
    query: str
    app_id: str
    collection_id: str
    top_k: int = Field(default=5, ge=1, le=20)
    filter_conditions: Optional[Dict[str, Any]] = None

class ContextResponse(BaseModel):
    context: str
    sources: List[SearchResult]

def get_retrieval():
    return state["retrieval"]

async def get_search_request(request: Request) -> SearchRequest:
    """Extract and validate search request from body."""
    body = await request.json()
    return SearchRequest(**body)

@router.post("", response_model=SearchResponse)
async def search(
    search_request: SearchRequest = Depends(get_search_request),
    key_info: Dict[str, Any] = Depends(require_scopes("read")),
):
    """Hybrid search (vector + lexical) with RRF. Requires read scope."""
    retrieval = get_retrieval()
    results = retrieval.search(
        app_id=search_request.app_id,
        collection_id=search_request.collection_id,
        query=search_request.query,
        top_k=search_request.top_k,
        filter_conditions=search_request.filter_conditions,
        use_hybrid=search_request.use_hybrid,
    )
    return SearchResponse(results=[
        SearchResult(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            content=r.content,
            score=r.score,
            rank=r.rank,
            retrieval_method=r.retrieval_method,
            payload=r.payload,
            source_uri=r.source_uri,
            chunk_index=r.chunk_index,
        ) for r in results
    ])

@router.post("/vector", response_model=SearchResponse)
async def search_vector(
    search_request: SearchRequest = Depends(get_search_request),
    key_info: Dict[str, Any] = Depends(require_scopes("read")),
):
    """Pure vector similarity search. Requires read scope."""
    retrieval = get_retrieval()
    results = retrieval.search_vector_only(
        app_id=search_request.app_id,
        collection_id=search_request.collection_id,
        query=search_request.query,
        top_k=search_request.top_k,
        filter_conditions=search_request.filter_conditions,
    )
    return SearchResponse(results=[
        SearchResult(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            content=r.content,
            score=r.score,
            rank=r.rank,
            retrieval_method=r.retrieval_method,
            payload=r.payload,
            source_uri=r.source_uri,
            chunk_index=r.chunk_index,
        ) for r in results
    ])

@router.post("/lexical", response_model=SearchResponse)
async def search_lexical(
    search_request: SearchRequest = Depends(get_search_request),
    key_info: Dict[str, Any] = Depends(require_scopes("read")),
):
    """Pure lexical (BM25) search. Requires read scope."""
    retrieval = get_retrieval()
    results = retrieval.search_lexical_only(
        app_id=search_request.app_id,
        collection_id=search_request.collection_id,
        query=search_request.query,
        top_k=search_request.top_k,
    )
    return SearchResponse(results=[
        SearchResult(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            content=r.content,
            score=r.score,
            rank=r.rank,
            retrieval_method=r.retrieval_method,
            payload=r.payload,
            source_uri=r.source_uri,
            chunk_index=r.chunk_index,
        ) for r in results
    ])

@router.post("/context", response_model=ContextResponse)
async def get_context(
    context_request: ContextRequest = Depends(get_search_request),  # ContextRequest is similar to SearchRequest
    key_info: Dict[str, Any] = Depends(require_scopes("read")),
):
    """Get formatted context for grounded generation. Requires read scope."""
    retrieval = get_retrieval()
    context, sources = retrieval.get_context(
        app_id=context_request.app_id,
        collection_id=context_request.collection_id,
        query=context_request.query,
        top_k=context_request.top_k,
        filter_conditions=context_request.filter_conditions,
    )
    return ContextResponse(
        context=context,
        sources=[
            SearchResult(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                content=r.content,
                score=r.score,
                rank=r.rank,
                retrieval_method=r.retrieval_method,
                payload=r.payload,
                source_uri=r.source_uri,
                chunk_index=r.chunk_index,
            ) for r in sources
        ]
    )
