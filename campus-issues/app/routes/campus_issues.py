from fastapi import APIRouter, Request, Depends, HTTPException, Form, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import os
import sys

# Ensure local-rag/src is on sys.path so we can reuse its core modules
# __file__ = .../campus-issues/app/routes/campus_issues.py
# 3 levels up reaches .../local-rag (routes -> app -> campus-issues -> local-rag)
_LOCALRAG = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _LOCALRAG not in sys.path:
    sys.path.insert(0, _LOCALRAG)

from src.core.sqlite_store import SQLiteStore
from src.core.retrieval import HybridRetrievalService
from src.core.ingestion import IngestionService
from src.core.embedding import EmbeddingProvider
from src.core.qdrant_store import QdrantStore
from app.core.campus_auth import CampusAuthManager

router = APIRouter(tags=["campus-issues"])

# State injection
state: Dict[str, Any] = {}

def set_state(s: Dict[str, Any]):
    global state
    state = s

# Templates — resolve path relative to this file so it works from any CWD
# __file__ = .../campus-issues/app/routes/campus_issues.py
# 3 levels up: app/routes -> app -> campus-issues
_TEMPLATES_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "templates"))
# Use a custom Jinja2 environment with cache_size=0 to avoid Jinja2 3.x cache bug with Python 3.14
from jinja2 import Environment, FileSystemLoader
_env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), cache_size=0, autoescape=True)
templates = Jinja2Templates(env=_env)

# Dependency: Get current user from session
async def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    session = request.cookies.get("session")
    if not session:
        return None
    auth: CampusAuthManager = state.get("campus_auth")
    if not auth:
        return None
    return auth.verify_session(session)

async def require_auth(user: Optional[Dict] = Depends(get_current_user)) -> Dict[str, Any]:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user

async def require_staff(user: Dict = Depends(require_auth)) -> Dict[str, Any]:
    if user["role"] not in ("staff", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff access required")
    return user

# =====================================================================
# Authentication Routes
# =====================================================================

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: Optional[Dict] = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})

@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    auth: CampusAuthManager = state.get("campus_auth")
    user = auth.authenticate(email, password)
    if not user:
        return templates.TemplateResponse(request, "login.html", {"error": "Invalid email or password"}, status_code=400)

    session = auth.create_session(user)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("session", session, httponly=True, samesite="lax", max_age=2592000)
    return response

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user: Optional[Dict] = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "register.html", {})

@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    if password != confirm_password:
        return templates.TemplateResponse(request, "register.html", {"error": "Passwords do not match"}, status_code=400)

    auth: CampusAuthManager = state.get("campus_auth")
    user = auth.register_user(username, email, password, "student")
    if not user:
        return templates.TemplateResponse(request, "register.html", {"error": "Username or email already registered"}, status_code=400)

    session = auth.create_session(user)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("session", session, httponly=True, samesite="lax", max_age=2592000)
    return response

@router.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response

# =====================================================================
# Student Routes — Ticket Submission & Tracking
# =====================================================================

@router.get("/", response_class=HTMLResponse)
async def student_dashboard(
    request: Request,
    user: Dict = Depends(require_auth)
):
    sqlite: SQLiteStore = state.get("sqlite")
    tickets = sqlite.get_tickets_by_reporter(user["user_id"])
    return templates.TemplateResponse(request, "student_dashboard.html", {"user": user, "tickets": tickets})

@router.get("/report", response_class=HTMLResponse)
async def report_page(
    request: Request,
    user: Dict = Depends(require_auth)
):
    return templates.TemplateResponse(request, "report.html", {"user": user})

@router.post("/report")
async def submit_report(
    request: Request,
    user: Dict = Depends(require_auth),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    building: str = Form(...),
    location: str = Form(...)
):
    sqlite: SQLiteStore = state.get("sqlite")
    
    # Check for duplicates via RAG
    retrieval: HybridRetrievalService = state.get("retrieval")
    similar = retrieval.search(
        app_id="campus-issues",
        collection_id="tickets",
        query=f"{title} {description}",
        top_k=3
    )
    
    duplicate_suggestions = []
    for r in similar:
        # RRF scores are ~1/(k+rank) where k=60, so max ~0.016. Use 0.01 threshold.
        if r.score > 0.01:
            # Extract ticket_id from document_id if it follows our pattern
            doc_id = r.document_id
            duplicate_suggestions.append({
                "ticket_id": doc_id,
                "title": r.content[:80],
                "score": round(r.score, 4)
            })

    # If duplicates found and user didn't confirm, show confirmation
    confirm = request.headers.get("HX-Trigger-Name") == "confirm-duplicates"
    if duplicate_suggestions and not confirm:
        return templates.TemplateResponse(request, "report.html", {
            "user": user,
            "title": title, "description": description,
            "category": category, "building": building, "location": location,
            "duplicate_suggestions": duplicate_suggestions,
            "show_duplicate_warning": True
        }, status_code=200)

    # Create ticket
    ticket_id = f"C-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    sqlite.create_ticket(ticket_id, user["user_id"], title, description,
                         category, building, location)

    # Index in RAG for future duplicate detection
    ingestion: IngestionService = state.get("ingestion")
    ingestion.ingest_text(
        app_id="campus-issues",
        collection_id="tickets",
        text=f"Title: {title}\nDescription: {description}\nCategory: {category}\nBuilding: {building}\nLocation: {location}",
        source_uri=f"ticket://{ticket_id}",
        document_id=ticket_id,
        source_type="campus_ticket",
        metadata={"reporter_id": user["user_id"], "status": "Submitted"}
    )

    return templates.TemplateResponse(request, "report.html", {
        "user": user,
        "success": True, "ticket_id": ticket_id
    })

@router.get("/ticket/{ticket_id}", response_class=HTMLResponse)
async def ticket_detail(
    request: Request,
    ticket_id: str,
    user: Dict = Depends(require_auth)
):
    sqlite: SQLiteStore = state.get("sqlite")
    ticket = sqlite.get_ticket(ticket_id)
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Students can only see their own tickets
    if user["role"] == "student" and ticket["reporter_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized to view this ticket")

    history = sqlite.get_ticket_history(ticket_id)
    return templates.TemplateResponse(request, "ticket_detail.html", {
        "user": user, "ticket": ticket, "history": history
    })

# =====================================================================
# Staff Routes — Dashboard & Management
# =====================================================================

@router.get("/staff", response_class=HTMLResponse)
async def staff_dashboard(
    request: Request,
    user: Dict = Depends(require_staff),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    building: Optional[str] = Query(None)
):
    sqlite: SQLiteStore = state.get("sqlite")
    tickets = sqlite.get_all_tickets(status=status, category=category, building=building)
    
    # Get stats
    all_tickets = sqlite.get_all_tickets()
    stats = {
        "total": len(all_tickets),
        "submitted": len([t for t in all_tickets if t["status"] == "Submitted"]),
        "in_progress": len([t for t in all_tickets if t["status"] == "In Progress"]),
        "resolved": len([t for t in all_tickets if t["status"] == "Resolved"]),
        "unresolved": len([t for t in all_tickets if t["status"] not in ("Resolved", "Closed", "Rejected", "Duplicate")]),
    }
    
    return templates.TemplateResponse(request, "staff_dashboard.html", {
        "user": user, "tickets": tickets, "stats": stats,
        "filter_status": status, "filter_category": category, "filter_building": building
    })

@router.get("/staff/ticket/{ticket_id}", response_class=HTMLResponse)
async def staff_ticket_detail(
    request: Request,
    ticket_id: str,
    user: Dict = Depends(require_staff)
):
    sqlite: SQLiteStore = state.get("sqlite")
    ticket = sqlite.get_ticket(ticket_id)
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    history = sqlite.get_ticket_history(ticket_id)
    return templates.TemplateResponse(request, "staff_ticket_detail.html", {
        "user": user, "ticket": ticket, "history": history
    })

@router.post("/staff/ticket/{ticket_id}/status")
async def update_ticket_status(
    request: Request,
    ticket_id: str,
    user: Dict = Depends(require_staff),
    new_status: str = Form(...),
    assigned_to: Optional[str] = Form(None),
    note: Optional[str] = Form(None)
):
    sqlite: SQLiteStore = state.get("sqlite")
    success = sqlite.update_ticket_status(ticket_id, new_status, user["user_id"], assigned_to, note)
    
    if not success:
        raise HTTPException(status_code=400, detail="Invalid status transition or ticket not found")
    
    # Update RAG index with new status
    ticket = sqlite.get_ticket(ticket_id)
    ingestion: IngestionService = state.get("ingestion")
    ingestion.ingest_text(
        app_id="campus-issues",
        collection_id="tickets",
        text=f"Title: {ticket['title']}\nDescription: {ticket['description']}\nCategory: {ticket['category']}\nBuilding: {ticket['building']}\nLocation: {ticket['location']}",
        source_uri=f"ticket://{ticket_id}",
        document_id=ticket_id,
        source_type="campus_ticket",
        metadata={"reporter_id": ticket["reporter_id"], "status": new_status}
    )
    
    return RedirectResponse(url=f"/staff/ticket/{ticket_id}", status_code=303)

@router.post("/staff/ticket/{ticket_id}/note")
async def add_ticket_note(
    request: Request,
    ticket_id: str,
    user: Dict = Depends(require_staff),
    note: str = Form(...),
    is_internal: bool = Form(True)
):
    sqlite: SQLiteStore = state.get("sqlite")
    sqlite.add_ticket_note(ticket_id, user["user_id"], note, is_internal)
    return RedirectResponse(url=f"/staff/ticket/{ticket_id}", status_code=303)

# =====================================================================
# Duplicate Check API (HTMX)
# =====================================================================

@router.post("/api/check-duplicates")
async def check_duplicates(
    request: Request,
    user: Dict = Depends(require_auth),
    title: str = Form(...),
    description: str = Form(...)
):
    retrieval: HybridRetrievalService = state.get("retrieval")
    similar = retrieval.search(
        app_id="campus-issues",
        collection_id="tickets",
        query=f"{title} {description}",
        top_k=5
    )
    
    suggestions = []
    for r in similar:
        if r.score > 0.6:
            suggestions.append({
                "ticket_id": r.document_id,
                "title": r.content[:100],
                "score": round(r.score, 2)
            })
    
    return {"duplicates": suggestions}