from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import uuid
import tempfile
import os
import shutil
import json

from src.core.auth import require_scopes

router = APIRouter(prefix="/ingest", tags=["ingestion"])

state: Dict[str, Any] = {}

def set_state(s: Dict[str, Any]):
    global state
    state = s

# Models
class IngestTextRequest(BaseModel):
    text: str
    source_uri: str
    document_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class IngestResponse(BaseModel):
    success: bool
    document_id: str
    chunks_created: int
    message: str
    content_hash: str

class BatchIngestRequest(BaseModel):
    documents: List[Dict[str, Any]]  # Each: text, source_uri, document_id, metadata

class BatchIngestResponse(BaseModel):
    results: List[IngestResponse]

def get_ingestion():
    return state["ingestion"]

@router.post("/text", response_model=IngestResponse)
async def ingest_text(
    request: IngestTextRequest,
    app_id: str = Query(...),
    collection_id: str = Query(...),
    key_info: Dict[str, Any] = Depends(require_scopes("write")),
):
    """Ingest raw text content. Requires write scope."""
    ingestion = get_ingestion()
    result = ingestion.ingest_text(
        app_id=app_id,
        collection_id=collection_id,
        text=request.text,
        source_uri=request.source_uri,
        document_id=request.document_id,
        metadata=request.metadata,
    )
    return IngestResponse(**result.__dict__)

@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    app_id: str = Form(...),
    collection_id: str = Form(...),
    document_id: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    key_info: Dict[str, Any] = Depends(require_scopes("write")),
):
    """Ingest an uploaded file. Requires write scope."""
    ingestion = get_ingestion()
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Check file size (max 50MB by default)
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file not allowed")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, 
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE} bytes"
        )
    
    # Validate file extension
    allowed_extensions = {'.txt', '.md', '.pdf', '.docx', '.html', '.json', '.jsonl', '.csv', '.yaml', '.yml', '.xml', '.py', '.js', '.ts', '.css', '.sql', '.sh', '.rs', '.go', '.java', '.cpp', '.c', '.h'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"File extension '{ext}' not allowed. Allowed: {', '.join(sorted(allowed_extensions))}"
        )
    
    # Parse metadata
    meta = json.loads(metadata) if metadata else {}
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        result = ingestion.ingest_file(
            app_id=app_id,
            collection_id=collection_id,
            file_path=tmp_path,
            source_uri=f"file://{file.filename}",
            document_id=document_id,
            metadata=meta,
        )
        return IngestResponse(**result.__dict__)
    finally:
        os.unlink(tmp_path)

@router.post("/batch", response_model=BatchIngestResponse)
async def ingest_batch(
    request: BatchIngestRequest,
    key_info: Dict[str, Any] = Depends(require_scopes("write")),
):
    """Batch ingest multiple documents. Requires write scope."""
    ingestion = get_ingestion()
    results = []
    for doc in request.documents:
        result = ingestion.ingest_text(
            app_id=doc.get("app_id", "default"),
            collection_id=doc.get("collection_id", "default"),
            text=doc.get("text", ""),
            source_uri=doc.get("source_uri", ""),
            document_id=doc.get("document_id"),
            metadata=doc.get("metadata"),
        )
        results.append(IngestResponse(**result.__dict__))
    return BatchIngestResponse(results=results)

@router.delete("/{app_id}/{collection_id}/{document_id}")
async def delete_document(
    app_id: str, 
    collection_id: str, 
    document_id: str,
    key_info: Dict[str, Any] = Depends(require_scopes("write")),
):
    """Delete a document and all its chunks. Requires write scope."""
    ingestion = get_ingestion()
    success = ingestion.delete_document(app_id, collection_id, document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"success": True, "message": "Document deleted"}