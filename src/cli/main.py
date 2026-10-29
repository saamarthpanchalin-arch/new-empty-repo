#!/usr/bin/env python3
"""CLI for Local RAG Knowledge Infrastructure."""

import argparse
import sys
import json
import os
from typing import Optional, List
import requests

class CLIClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")
    
    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        resp = requests.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()

def cmd_health(args):
    client = CLIClient(args.url)
    result = client._request("GET", "/health/")
    print(json.dumps(result, indent=2))

def cmd_ready(args):
    client = CLIClient(args.url)
    result = client._request("GET", "/health/ready")
    print(json.dumps(result, indent=2))

def cmd_app_create(args):
    client = CLIClient(args.url)
    result = client._request("POST", "/applications/", json={
        "id": args.id,
        "name": args.name,
        "description": args.description or "",
    })
    print(json.dumps(result, indent=2))

def cmd_app_list(args):
    client = CLIClient(args.url)
    result = client._request("GET", "/applications/")
    print(json.dumps(result, indent=2))

def cmd_collection_create(args):
    client = CLIClient(args.url)
    result = client._request("POST", f"/applications/{args.app_id}/collections", json={
        "id": args.id,
        "name": args.name,
        "description": args.description or "",
        "embedding_model": args.embedding_model,
        "chunk_strategy": args.chunk_strategy,
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
    })
    print(json.dumps(result, indent=2))

def cmd_collection_list(args):
    client = CLIClient(args.url)
    result = client._request("GET", f"/applications/{args.app_id}/collections")
    print(json.dumps(result, indent=2))

def cmd_ingest_text(args):
    client = CLIClient(args.url)
    result = client._request("POST", "/ingest/text", json={
        "text": args.text,
        "source_uri": args.source_uri,
        "document_id": args.document_id,
        "metadata": json.loads(args.metadata) if args.metadata else {},
    })
    print(json.dumps(result, indent=2))

def cmd_ingest_file(args):
    client = CLIClient(args.url)
    import os
    with open(args.file, "rb") as f:
        files = {"file": (os.path.basename(args.file), f)}
        data = {
            "app_id": args.app_id,
            "collection_id": args.collection_id,
            "document_id": args.document_id or "",
            "metadata": json.dumps(json.loads(args.metadata) if args.metadata else {}),
        }
        resp = requests.post(f"{args.url}/ingest/file", files=files, data=data)
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))

def cmd_search(args):
    client = CLIClient(args.url)
    result = client._request("POST", "/search/", json={
        "query": args.query,
        "app_id": args.app_id,
        "collection_id": args.collection_id,
        "top_k": args.top_k,
        "use_hybrid": not args.vector_only,
    })
    print(json.dumps(result, indent=2))

def cmd_ask(args):
    client = CLIClient(args.url)
    result = client._request("POST", "/generate/ask", json={
        "query": args.query,
        "app_id": args.app_id,
        "collection_id": args.collection_id,
        "top_k": args.top_k,
        "model": args.model,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
    })
    print(json.dumps(result, indent=2))

def cmd_feedback(args):
    client = CLIClient(args.url)
    result = client._request("POST", "/feedback/", json={
        "app_id": args.app_id,
        "collection_id": args.collection_id,
        "query": args.query,
        "feedback_type": args.feedback_type,
        "rating": args.rating,
        "explanation": args.explanation,
    })
    print(json.dumps(result, indent=2))

def cmd_reviews_list(args):
    client = CLIClient(args.url)
    result = client._request("GET", f"/feedback/{args.app_id}/pending")
    print(json.dumps(result, indent=2))

def cmd_annotation_create(args):
    client = CLIClient(args.url)
    result = client._request("POST", "/feedback/annotations", json={
        "app_id": args.app_id,
        "collection_id": args.collection_id,
        "question": args.question,
        "verified_answer": args.answer,
        "review_case_id": args.case_id,
        "created_by": args.created_by,
    })
    print(json.dumps(result, indent=2))

def cmd_status(args):
    """System overview: health, counts, embedding config."""
    client = CLIClient(args.url)
    try:
        health = client._request("GET", "/health/")
        print("=== SYSTEM STATUS ===")
        print(f"Service: {health.get('service', 'unknown')}")
        print(f"Version: {health.get('version', 'unknown')}")
        print(f"Status: {health.get('status', 'unknown')}")
    except Exception as e:
        print(f"Health check failed: {e}", file=sys.stderr)

def cmd_projects(args):
    """List website projects (applications)."""
    client = CLIClient(args.url)
    result = client._request("GET", "/applications/")
    print("=== WEBSITE PROJECTS ===")
    if isinstance(result, list):
        for app in result:
            print(f"  - {app.get('id')}: {app.get('name')} ({app.get('description', 'no description')})")
    else:
        print(json.dumps(result, indent=2))

def cmd_sources(args):
    """List configured sources."""
    client = CLIClient(args.url)
    app_id = args.app_id if hasattr(args, 'app_id') else None
    path = "/sources/"
    if app_id:
        path += f"?application_id={app_id}"
    result = client._request("GET", path)
    print("=== SOURCES ===")
    if isinstance(result, list):
        for src in result:
            print(f"  - {src.get('id')}: {src.get('name')} ({src.get('organization')}) [{src.get('source_type')}]")
            print(f"    URL: {src.get('official_url')}")
            print(f"    Last sync: {src.get('last_sync_at', 'never')} ({src.get('last_sync_status', 'unknown')})")
    else:
        print(json.dumps(result, indent=2))

def cmd_sync(args):
    """Trigger synchronization for a source."""
    client = CLIClient(args.url)
    # For now, run local ingestion script if available
    print(f"Triggering sync for source: {args.source_id}")
    # This would call a sync endpoint when available
    print("Note: Synchronization endpoint not yet exposed. Use the dashboard or direct API.")

def cmd_collections(args):
    """List collections."""
    client = CLIClient(args.url)
    app_id = args.app_id if hasattr(args, 'app_id') else None
    if not app_id:
        print("Error: --app-id required", file=sys.stderr)
        sys.exit(1)
    result = client._request("GET", f"/applications/{app_id}/collections")
    print("=== COLLECTIONS ===")
    if isinstance(result, list):
        for col in result:
            print(f"  - {col.get('id')}: {col.get('name')} (dim={col.get('embedding_dim')})")
    else:
        print(json.dumps(result, indent=2))

def cmd_documents(args):
    """List documents."""
    client = CLIClient(args.url)
    app_id = args.app_id if hasattr(args, 'app_id') else None
    if not app_id:
        print("Error: --app-id required", file=sys.stderr)
        sys.exit(1)
    # Use direct SQLite access for document listing
    import sqlite3
    conn = sqlite3.connect("data/metadata.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM documents WHERE application_id = ?",
        (app_id,)
    ).fetchall()
    conn.close()
    print("=== DOCUMENTS ===")
    for r in rows:
        d = dict(r)
        print(f"  - {d.get('id')}: {d.get('source_uri')}")
        print(f"    Version: {d.get('document_version')}, Hash: {d.get('content_hash')}, Status: {d.get('status')}")

def cmd_add(args):
    """Add a document file."""
    client = CLIClient(args.url)
    import os
    with open(args.file, "rb") as f:
        files = {"file": (os.path.basename(args.file), f)}
        data = {
            "app_id": args.app_id,
            "collection_id": args.collection_id,
            "document_id": args.document_id or "",
            "metadata": "{}",
        }
        resp = requests.post(f"{args.url}/ingest/file", files=files, data=data)
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))

def cmd_update(args):
    """Update a document file (re-ingest)."""
    client = CLIClient(args.url)
    import os
    with open(args.file, "rb") as f:
        files = {"file": (os.path.basename(args.file), f)}
        data = {
            "app_id": args.app_id,
            "collection_id": args.collection_id,
            "document_id": args.document_id or "",
            "metadata": "{}",
        }
        resp = requests.post(f"{args.url}/ingest/file", files=files, data=data)
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))

def cmd_delete(args):
    """Delete a document."""
    client = CLIClient(args.url)
    result = client._request("DELETE", f"/documents/{args.app_id}/{args.collection_id}/{args.document_id}")
    print(json.dumps(result, indent=2))

def cmd_jobs(args):
    """List ingestion jobs."""
    client = CLIClient(args.url)
    print("=== INGESTION JOBS ===")
    print("(Job monitoring endpoint not yet exposed. Check the dashboard for real-time status.)")

def cmd_doctor(args):
    """Run diagnostics."""
    client = CLIClient(args.url)
    print("=== DOCTOR ===")
    try:
        ready = client._request("GET", "/health/ready")
        print(json.dumps(ready, indent=2))
    except Exception as e:
        print(f"Health check failed: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        prog="local-rag",
        description="Local RAG Knowledge Infrastructure CLI"
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="API base URL")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Health
    subparsers.add_parser("health", help="Health check").set_defaults(func=cmd_health)
    subparsers.add_parser("ready", help="Readiness check").set_defaults(func=cmd_ready)

    # Applications
    p_app = subparsers.add_parser("app", help="Application management")
    app_sub = p_app.add_subparsers(dest="app_cmd", required=True)
    
    p_create = app_sub.add_parser("create", help="Create application")
    p_create.add_argument("--id", required=True)
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--description", default="")
    p_create.set_defaults(func=cmd_app_create)

    p_list = app_sub.add_parser("list", help="List applications")
    p_list.set_defaults(func=cmd_app_list)

    # Collections
    p_col = subparsers.add_parser("collection", help="Collection management")
    col_sub = p_col.add_subparsers(dest="col_cmd", required=True)

    p_cc = col_sub.add_parser("create", help="Create collection")
    p_cc.add_argument("--app-id", required=True)
    p_cc.add_argument("--id", required=True)
    p_cc.add_argument("--name", required=True)
    p_cc.add_argument("--description", default="")
    p_cc.add_argument("--embedding-model", default="BAAI/bge-small-en-v1.5")
    p_cc.add_argument("--chunk-strategy", default="recursive")
    p_cc.add_argument("--chunk-size", type=int, default=500)
    p_cc.add_argument("--chunk-overlap", type=int, default=50)
    p_cc.set_defaults(func=cmd_collection_create)

    p_cl = col_sub.add_parser("list", help="List collections")
    p_cl.add_argument("--app-id", required=True)
    p_cl.set_defaults(func=cmd_collection_list)

    # Ingestion
    p_ing = subparsers.add_parser("ingest", help="Ingestion")
    ing_sub = p_ing.add_subparsers(dest="ingest_cmd", required=True)

    p_it = ing_sub.add_parser("text", help="Ingest text")
    p_it.add_argument("--app-id", required=True)
    p_it.add_argument("--collection-id", required=True)
    p_it.add_argument("--text", required=True)
    p_it.add_argument("--source-uri", required=True)
    p_it.add_argument("--document-id")
    p_it.add_argument("--metadata", default="{}")
    p_it.set_defaults(func=cmd_ingest_text)

    p_if = ing_sub.add_parser("file", help="Ingest file")
    p_if.add_argument("--app-id", required=True)
    p_if.add_argument("--collection-id", required=True)
    p_if.add_argument("--file", required=True)
    p_if.add_argument("--document-id")
    p_if.add_argument("--metadata", default="{}")
    p_if.set_defaults(func=cmd_ingest_file)

    # Search
    p_search = subparsers.add_parser("search", help="Search")
    p_search.add_argument("--app-id", required=True)
    p_search.add_argument("--collection-id", required=True)
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--top-k", type=int, default=10)
    p_search.add_argument("--vector-only", action="store_true", help="Use vector search only")
    p_search.set_defaults(func=cmd_search)

    # Ask
    p_ask = subparsers.add_parser("ask", help="Ask a question (grounded generation)")
    p_ask.add_argument("--app-id", required=True)
    p_ask.add_argument("--collection-id", required=True)
    p_ask.add_argument("--query", required=True)
    p_ask.add_argument("--top-k", type=int, default=5)
    p_ask.add_argument("--model")
    p_ask.add_argument("--max-tokens", type=int, default=512)
    p_ask.add_argument("--temperature", type=float, default=0.1)
    p_ask.set_defaults(func=cmd_ask)

    # Feedback
    p_fb = subparsers.add_parser("feedback", help="Submit feedback")
    p_fb.add_argument("--app-id", required=True)
    p_fb.add_argument("--collection-id", required=True)
    p_fb.add_argument("--query", required=True)
    p_fb.add_argument("--feedback-type", required=True, choices=[
        "helpful", "not_helpful", "correct", "incorrect", "relevant", "irrelevant",
        "missing_info", "outdated", "wrong_source", "hallucination", "duplicate", "wrong_extraction"
    ])
    p_fb.add_argument("--rating", type=int, choices=[1,2,3,4,5])
    p_fb.add_argument("--explanation")
    p_fb.set_defaults(func=cmd_feedback)

    p_reviews = subparsers.add_parser("reviews", help="List pending reviews")
    p_reviews.add_argument("--app-id", required=True)
    p_reviews.set_defaults(func=cmd_reviews_list)

    # Annotations
    p_ann = subparsers.add_parser("annotation", help="Create verified annotation")
    p_ann.add_argument("--app-id", required=True)
    p_ann.add_argument("--collection-id", required=True)
    p_ann.add_argument("--question", required=True)
    p_ann.add_argument("--answer", required=True)
    p_ann.add_argument("--case-id")
    p_ann.add_argument("--created-by", default="admin")
    p_ann.set_defaults(func=cmd_annotation_create)

    # Status
    p_status = subparsers.add_parser("status", help="System overview")
    p_status.set_defaults(func=cmd_status)

    # Projects
    p_projects = subparsers.add_parser("projects", help="List website projects")
    p_projects.set_defaults(func=cmd_projects)

    # Sources
    p_sources = subparsers.add_parser("sources", help="List configured sources")
    p_sources.add_argument("--app-id", default=None)
    p_sources.set_defaults(func=cmd_sources)

    # Sync
    p_sync = subparsers.add_parser("sync", help="Trigger synchronization")
    p_sync.add_argument("--source-id", required=True)
    p_sync.set_defaults(func=cmd_sync)

    # Collections (alias)
    p_collections = subparsers.add_parser("collections", help="List collections")
    p_collections.add_argument("--app-id", required=True)
    p_collections.set_defaults(func=cmd_collections)

    # Documents
    p_docs = subparsers.add_parser("documents", help="List documents")
    p_docs.add_argument("--app-id", required=True)
    p_docs.set_defaults(func=cmd_documents)

    # Add
    p_add = subparsers.add_parser("add", help="Add a document file")
    p_add.add_argument("--app-id", required=True)
    p_add.add_argument("--collection-id", required=True)
    p_add.add_argument("--file", required=True)
    p_add.add_argument("--document-id", default=None)
    p_add.set_defaults(func=cmd_add)

    # Update
    p_update = subparsers.add_parser("update", help="Update a document file")
    p_update.add_argument("--app-id", required=True)
    p_update.add_argument("--collection-id", required=True)
    p_update.add_argument("--file", required=True)
    p_update.add_argument("--document-id", default=None)
    p_update.set_defaults(func=cmd_update)

    # Delete
    p_delete = subparsers.add_parser("delete", help="Delete a document")
    p_delete.add_argument("--app-id", required=True)
    p_delete.add_argument("--collection-id", required=True)
    p_delete.add_argument("--document-id", required=True)
    p_delete.set_defaults(func=cmd_delete)

    # Jobs
    p_jobs = subparsers.add_parser("jobs", help="List ingestion jobs")
    p_jobs.set_defaults(func=cmd_jobs)

    # Doctor
    p_doctor = subparsers.add_parser("doctor", help="Run diagnostics")
    p_doctor.set_defaults(func=cmd_doctor)

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()