from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import uuid

from src.core.auth import require_scopes

router = APIRouter(prefix="/feedback", tags=["feedback"])

state: Dict[str, Any] = {}

def set_state(s: Dict[str, Any]):
    global state
    state = s

# Models
class FeedbackRequest(BaseModel):
    app_id: str
    collection_id: str
    query: str
    response: Optional[str] = None
    retrieved_chunks: List[Dict[str, Any]] = []
    feedback_type: str = Field(..., pattern=r"^(helpful|not_helpful|correct|incorrect|relevant|irrelevant|missing_info|outdated|wrong_source|hallucination|duplicate|wrong_extraction)$")
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    explanation: Optional[str] = None

class FeedbackResponse(BaseModel):
    id: str
    status: str

class ReviewCaseResponse(BaseModel):
    id: str
    application_id: str
    collection_id: str
    query: str
    response: Optional[str]
    retrieved_chunks_json: str
    feedback_type: str
    rating: Optional[int]
    explanation: Optional[str]
    status: str
    resolution_notes: Optional[str]
    reviewer_id: Optional[str]
    created_at: str
    updated_at: str

class ResolveReviewRequest(BaseModel):
    status: str = Field(..., pattern=r"^(reviewed|accepted|rejected|resolved)$")
    notes: Optional[str] = None
    reviewer_id: str

class AnnotationCreate(BaseModel):
    app_id: str
    collection_id: str
    question: str
    verified_answer: str
    review_case_id: Optional[str] = None
    source_refs: Optional[List[Dict[str, Any]]] = None
    created_by: str = "admin"

class AnnotationResponse(BaseModel):
    id: str
    status: str

def get_sqlite():
    return state["sqlite"]

@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    key_info: Dict[str, Any] = Depends(require_scopes("write")),
):
    """Submit feedback on a retrieval/generation result. Requires write scope."""
    sqlite = get_sqlite()
    case_id = str(uuid.uuid4())[:16]
    result = sqlite.add_feedback(
        case_id=case_id,
        app_id=request.app_id,
        collection_id=request.collection_id,
        query=request.query,
        retrieved_chunks=request.retrieved_chunks,
        feedback_type=request.feedback_type,
        response=request.response,
        rating=request.rating,
        explanation=request.explanation,
    )
    return FeedbackResponse(**result)

@router.get("/{app_id}/pending")
async def list_pending_reviews(
    app_id: str,
    key_info: Dict[str, Any] = Depends(require_scopes("read")),
):
    """List pending review cases for an application. Requires read scope."""
    sqlite = get_sqlite()
    with sqlite.get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM review_cases WHERE application_id = ? AND status = 'pending' ORDER BY created_at DESC",
            (app_id,)
        ).fetchall()
    return [ReviewCaseResponse(**dict(row)) for row in rows]

@router.get("/{app_id}/all")
async def list_all_reviews(
    app_id: str,
    key_info: Dict[str, Any] = Depends(require_scopes("read")),
):
    """List all review cases for an application. Requires read scope."""
    sqlite = get_sqlite()
    with sqlite.get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM review_cases WHERE application_id = ? ORDER BY created_at DESC",
            (app_id,)
        ).fetchall()
    return [ReviewCaseResponse(**dict(row)) for row in rows]

@router.post("/{app_id}/cases/{case_id}/resolve")
async def resolve_review(
    app_id: str,
    case_id: str,
    request: ResolveReviewRequest,
    key_info: Dict[str, Any] = Depends(require_scopes("write")),
):
    """Resolve a review case. Requires write scope."""
    sqlite = get_sqlite()
    
    # Verify case belongs to app
    with sqlite.get_connection() as conn:
        row = conn.execute("SELECT * FROM review_cases WHERE id = ? AND application_id = ?", (case_id, app_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Review case not found")
    
    sqlite.resolve_review_case(case_id, request.status, request.notes or "", request.reviewer_id)
    return {"success": True, "message": f"Case {case_id} resolved as {request.status}"}

@router.post("/annotations", response_model=AnnotationResponse)
async def create_annotation(
    request: AnnotationCreate,
    key_info: Dict[str, Any] = Depends(require_scopes("write")),
):
    """Create a verified annotation/Q&A entry. Requires write scope."""
    sqlite = get_sqlite()
    annotation_id = str(uuid.uuid4())[:16]
    result = sqlite.add_annotation(
        annotation_id=annotation_id,
        app_id=request.app_id,
        collection_id=request.collection_id,
        question=request.question,
        verified_answer=request.verified_answer,
        review_case_id=request.review_case_id,
        source_refs=request.source_refs,
        created_by=request.created_by,
    )
    return AnnotationResponse(**result)

@router.get("/annotations/{app_id}/{collection_id}")
async def list_annotations(
    app_id: str,
    collection_id: str,
    key_info: Dict[str, Any] = Depends(require_scopes("read")),
):
    """List verified annotations for a collection. Requires read scope."""
    sqlite = get_sqlite()
    with sqlite.get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM annotations WHERE application_id = ? AND collection_id = ? ORDER BY created_at DESC",
            (app_id, collection_id)
        ).fetchall()
    return [dict(row) for row in rows]