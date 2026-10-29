import sqlite3
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

class SQLiteStore:
    def __init__(self, db_path: str = "data/metadata.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            # Applications
            conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                api_key_hash TEXT,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # Collections
            conn.execute("""
            CREATE TABLE IF NOT EXISTS collections (
                id TEXT NOT NULL,
                application_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                embedding_model TEXT NOT NULL,
                embedding_dim INTEGER NOT NULL,
                chunk_strategy TEXT NOT NULL,
                chunk_size INTEGER NOT NULL,
                chunk_overlap INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (application_id, id),
                FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
            );
            """)

            # Documents
            conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT NOT NULL,
                application_id TEXT NOT NULL,
                collection_id TEXT NOT NULL,
                source_uri TEXT NOT NULL,
                source_type TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                document_version INTEGER NOT NULL DEFAULT 1,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                access_scope TEXT NOT NULL DEFAULT 'private',
                status TEXT NOT NULL DEFAULT 'indexed',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (application_id, collection_id, id),
                FOREIGN KEY (application_id, collection_id) REFERENCES collections(application_id, id) ON DELETE CASCADE
            );
            """)

            # Chunks metadata
            conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL,
                collection_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                start_offset INTEGER,
                end_offset INTEGER,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (application_id, collection_id, document_id) REFERENCES documents(application_id, collection_id, id) ON DELETE CASCADE
            );
            """)

            # FTS5 Lexical Search Table
            conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                chunk_id UNINDEXED,
                application_id UNINDEXED,
                collection_id UNINDEXED,
                content
            );
            """)

            # Review cases & Feedback
            conn.execute("""
            CREATE TABLE IF NOT EXISTS review_cases (
                id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL,
                collection_id TEXT NOT NULL,
                query TEXT NOT NULL,
                response TEXT,
                retrieved_chunks_json TEXT NOT NULL,
                feedback_type TEXT NOT NULL,
                rating INTEGER,
                explanation TEXT,
                status TEXT NOT NULL DEFAULT 'pending', -- pending, reviewed, accepted, rejected, resolved
                resolution_notes TEXT,
                reviewer_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
            );
            """)

            # Annotations & Corrections (Verified facts/Q&A)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS annotations (
                id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL,
                collection_id TEXT NOT NULL,
                review_case_id TEXT,
                question TEXT,
                verified_answer TEXT NOT NULL,
                source_references_json TEXT,
                status TEXT NOT NULL DEFAULT 'approved',
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE,
                FOREIGN KEY (review_case_id) REFERENCES review_cases(id) ON DELETE SET NULL
            );
            """)

            # Audit logs
            conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id TEXT,
                action TEXT NOT NULL,
                details_json TEXT,
                timestamp TEXT NOT NULL
            );
            """)

            # API Keys
            conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                key_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                application_id TEXT NOT NULL,
                scopes_json TEXT NOT NULL DEFAULT '["read", "write"]',
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                revoked BOOLEAN NOT NULL DEFAULT FALSE,
                FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
            );
            """)

            # Sources
            conn.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL,
                name TEXT NOT NULL,
                organization TEXT,
                official_url TEXT,
                api_doc_url TEXT,
                source_type TEXT,
                auth_type TEXT,
                auth_secret_name TEXT,
                license TEXT,
                attribution TEXT,
                refresh_interval_minutes INTEGER,
                last_sync_at TEXT,
                last_sync_status TEXT,
                last_sync_error TEXT,
                health_status TEXT,
                config_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
            );
            """)

            # --- Campus Issues Tables ---
            # Users
            conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student', -- student, staff, admin
                created_at TEXT NOT NULL
            );
            """)

            # Tickets
            conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                reporter_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                building TEXT NOT NULL,
                location TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Submitted',
                assigned_to TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (reporter_id) REFERENCES users(id)
            );
            """)

            # Ticket History
            conn.execute("""
            CREATE TABLE IF NOT EXISTS ticket_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
                FOREIGN KEY (actor_id) REFERENCES users(id)
            );
            """)

            conn.commit()

    # Application management
    def register_application(self, app_id: str, name: str, description: Optional[str] = None, api_key_hash: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO applications (id, name, api_key_hash, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (app_id, name, api_key_hash, description, now, now)
            )
            conn.commit()
        return {"id": app_id, "name": name, "description": description, "created_at": now}

    def get_application(self, app_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
            return dict(row) if row else None

    # Collection management
    def create_collection(
        self,
        app_id: str,
        collection_id: str,
        name: str,
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        embedding_dim: int = 384,
        chunk_strategy: str = "recursive",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO collections 
                (id, application_id, name, description, embedding_model, embedding_dim, chunk_strategy, chunk_size, chunk_overlap, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (collection_id, app_id, name, description, embedding_model, embedding_dim, chunk_strategy, chunk_size, chunk_overlap, now, now)
            )
            conn.commit()
        return {
            "id": collection_id,
            "application_id": app_id,
            "name": name,
            "embedding_model": embedding_model,
            "embedding_dim": embedding_dim,
            "chunk_strategy": chunk_strategy,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "created_at": now
        }

    def get_collection(self, app_id: str, collection_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM collections WHERE application_id = ? AND id = ?", (app_id, collection_id)).fetchone()
            return dict(row) if row else None

    # Document management
    def save_document(
        self,
        app_id: str,
        collection_id: str,
        doc_id: str,
        source_uri: str,
        source_type: str,
        content_hash: str,
        metadata: Dict[str, Any],
        access_scope: str = "private",
        version: int = 1
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata)
        with self.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO documents
                (id, application_id, collection_id, source_uri, source_type, content_hash, document_version, metadata_json, access_scope, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'indexed', ?, ?)""",
                (doc_id, app_id, collection_id, source_uri, source_type, content_hash, version, metadata_json, access_scope, now, now)
            )
            conn.commit()
        return {"id": doc_id, "version": version, "content_hash": content_hash}

    def get_document(self, app_id: str, collection_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE application_id = ? AND collection_id = ? AND id = ?",
                (app_id, collection_id, doc_id)
            ).fetchone()
            if row:
                d = dict(row)
                d['metadata'] = json.loads(d['metadata_json'])
                return d
            return None

    def delete_document_chunks(self, app_id: str, collection_id: str, doc_id: str):
        """Delete chunks for a document (used during re-ingestion)."""
        with self.get_connection() as conn:
            # Delete from FTS5 first
            conn.execute(
                "DELETE FROM chunks_fts WHERE chunk_id IN (SELECT chunk_id FROM chunks WHERE application_id=? AND collection_id=? AND document_id=?)",
                (app_id, collection_id, doc_id)
            )
            # Delete from chunks table
            conn.execute(
                "DELETE FROM chunks WHERE application_id=? AND collection_id=? AND document_id=?",
                (app_id, collection_id, doc_id)
            )
            conn.commit()

    def delete_document(self, app_id: str, collection_id: str, doc_id: str):
        """Delete a document and all its chunks from SQLite."""
        # Count chunks before deletion for audit
        with self.get_connection() as conn:
            count_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM chunks WHERE application_id=? AND collection_id=? AND document_id=?",
                (app_id, collection_id, doc_id)
            ).fetchone()
            chunk_count = count_row['cnt'] if count_row else 0

        with self.get_connection() as conn:
            # Delete from FTS5 first
            conn.execute(
                "DELETE FROM chunks_fts WHERE chunk_id IN (SELECT chunk_id FROM chunks WHERE application_id=? AND collection_id=? AND document_id=?)",
                (app_id, collection_id, doc_id)
            )
            # Delete from chunks table
            conn.execute(
                "DELETE FROM chunks WHERE application_id=? AND collection_id=? AND document_id=?",
                (app_id, collection_id, doc_id)
            )
            # Delete document metadata
            conn.execute(
                "DELETE FROM documents WHERE application_id=? AND collection_id=? AND id=?",
                (app_id, collection_id, doc_id)
            )
            conn.commit()

        # Audit log
        self.log_audit(app_id, "document_deleted", {
            "document_id": doc_id,
            "collection_id": collection_id,
            "chunks_removed": chunk_count,
        })

    def save_chunk(
        self,
        chunk_id: str,
        app_id: str,
        collection_id: str,
        doc_id: str,
        chunk_index: int,
        content: str,
        content_hash: str,
        start_offset: Optional[int] = None,
        end_offset: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        now = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata or {})
        with self.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO chunks
                (chunk_id, application_id, collection_id, document_id, chunk_index, content, content_hash, start_offset, end_offset, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (chunk_id, app_id, collection_id, doc_id, chunk_index, content, content_hash, start_offset, end_offset, metadata_json, now)
            )
            # Index in FTS5 (use INSERT OR REPLACE for idempotency)
            conn.execute(
                "INSERT OR REPLACE INTO chunks_fts (chunk_id, application_id, collection_id, content) VALUES (?, ?, ?, ?)",
                (chunk_id, app_id, collection_id, content)
            )
            conn.commit()

    # Lexical Search
    def search_lexical(self, app_id: str, collection_id: str, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        # FTS5 query - wrap in quotes to treat as phrase, handle special chars
        # Replace special characters that FTS5 treats as operators
        import re
        escaped_query = re.sub(r'[^\w\s]', ' ', query)  # Remove punctuation
        # Use simple term matching with OR between words
        terms = escaped_query.split()
        if not terms:
            return []
        # Build OR query
        fts_query = " OR ".join(f'"{term}"' for term in terms)
        
        with self.get_connection() as conn:
            rows = conn.execute(
                """SELECT fts.chunk_id, c.content, c.document_id, c.chunk_index, c.metadata_json, fts.rank
                FROM chunks_fts fts
                JOIN chunks c ON fts.chunk_id = c.chunk_id
                WHERE fts.application_id = ? AND fts.collection_id = ? AND chunks_fts MATCH ?
                ORDER BY fts.rank ASC
                LIMIT ?""",
                (app_id, collection_id, fts_query, top_k)
            ).fetchall()
            results = []
            for r in rows:
                res = dict(r)
                res['metadata'] = json.loads(res['metadata_json'])
                results.append(res)
            return results

    # Review & Feedback
    def add_feedback(
        self,
        case_id: str,
        app_id: str,
        collection_id: str,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        feedback_type: str,
        response: Optional[str] = None,
        rating: Optional[int] = None,
        explanation: Optional[str] = None
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        chunks_json = json.dumps(retrieved_chunks)
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO review_cases
                (id, application_id, collection_id, query, response, retrieved_chunks_json, feedback_type, rating, explanation, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (case_id, app_id, collection_id, query, response, chunks_json, feedback_type, rating, explanation, now, now)
            )
            conn.commit()
        self.log_audit(app_id, "feedback_submitted", {
            "case_id": case_id,
            "collection_id": collection_id,
            "feedback_type": feedback_type,
            "rating": rating,
        })
        return {"id": case_id, "status": "pending"}

    def resolve_review_case(self, case_id: str, status: str, notes: str, reviewer_id: str):
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE review_cases SET status = ?, resolution_notes = ?, reviewer_id = ?, updated_at = ? WHERE id = ?",
                (status, notes, reviewer_id, now, case_id)
            )
            conn.commit()
        self.log_audit(None, "review_resolved", {
            "case_id": case_id,
            "status": status,
            "reviewer_id": reviewer_id,
        })

    def add_annotation(
        self,
        annotation_id: str,
        app_id: str,
        collection_id: str,
        question: str,
        verified_answer: str,
        review_case_id: Optional[str] = None,
        source_refs: Optional[List[Dict[str, Any]]] = None,
        created_by: str = "admin"
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        refs_json = json.dumps(source_refs or [])
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO annotations
                (id, application_id, collection_id, review_case_id, question, verified_answer, source_references_json, status, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'approved', ?, ?)""",
                (annotation_id, app_id, collection_id, review_case_id, question, verified_answer, refs_json, created_by, now)
            )
            conn.commit()
        
        self.log_audit(app_id, "annotation_created", {
            "annotation_id": annotation_id,
            "collection_id": collection_id,
            "review_case_id": review_case_id,
            "question_preview": question[:100],
        })
        return {"id": annotation_id, "status": "approved"}

    def get_documents(self, app_id: str, collection_id: str) -> List[Dict[str, Any]]:
        """Get all documents in a collection."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE application_id = ? AND collection_id = ?",
                (app_id, collection_id)
            ).fetchall()
            results = []
            for r in rows:
                doc = dict(r)
                doc['metadata'] = json.loads(doc['metadata_json'])
                results.append(doc)
            return results

    def get_chunks_for_document(self, app_id: str, collection_id: str, document_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """SELECT c.*, f.rank
                FROM chunks c
                LEFT JOIN chunks_fts f ON c.chunk_id = f.chunk_id
                WHERE c.application_id = ? AND c.collection_id = ? AND c.document_id = ?
                ORDER BY c.chunk_index""",
                (app_id, collection_id, document_id)
            ).fetchall()
            results = []
            for r in rows:
                chunk = dict(r)
                chunk['metadata'] = json.loads(chunk['metadata_json'])
                results.append(chunk)
            return results

    def log_audit(self, app_id: Optional[str], action: str, details: Optional[Dict[str, Any]] = None):
        """Log an audit event. Never logs raw API keys or sensitive content."""
        now = datetime.now(timezone.utc).isoformat()
        # Sanitize details - never log raw keys or full document content
        safe_details = {}
        if details:
            for k, v in details.items():
                if 'key' in k.lower() or 'secret' in k.lower() or 'token' in k.lower():
                    safe_details[k] = "***REDACTED***"
                elif isinstance(v, str) and len(v) > 500:
                    safe_details[k] = v[:500] + "...[truncated]"
                else:
                    safe_details[k] = v
        details_json = json.dumps(safe_details) if safe_details else None
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO audit_logs (application_id, action, details_json, timestamp) VALUES (?, ?, ?, ?)",
                (app_id, action, details_json, now)
            )
            conn.commit()

    def get_audit_logs(self, app_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit logs, optionally filtered by application."""
        with self.get_connection() as conn:
            if app_id:
                rows = conn.execute(
                    "SELECT * FROM audit_logs WHERE application_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (app_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    # ==============================================================
    # Campus Issues — Users
    # ==============================================================
    def create_user(self, user_id: str, username: str, email: str, password_hash: str, role: str = "student") -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO users (id, username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, email, password_hash, role, now)
            )
            conn.commit()
        return {"id": user_id, "username": username, "email": email, "role": role, "created_at": now}

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            return dict(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return dict(row) if row else None

    # ==============================================================
    # Campus Issues — Tickets
    # ==============================================================
    def create_ticket(self, ticket_id: str, reporter_id: str, title: str, description: str,
                      category: str, building: str, location: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO tickets (id, reporter_id, title, description, category, building, location, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Submitted', ?, ?)""",
                (ticket_id, reporter_id, title, description, category, building, location, now, now)
            )
            conn.commit()
        self.log_ticket_history(ticket_id, reporter_id, "created", f"Ticket created: {title}")
        return {"id": ticket_id, "status": "Submitted", "created_at": now}

    def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            return dict(row) if row else None

    def get_tickets_by_reporter(self, reporter_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM tickets WHERE reporter_id = ? ORDER BY created_at DESC LIMIT ?",
                (reporter_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_tickets(self, status: Optional[str] = None, category: Optional[str] = None,
                        building: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            query = "SELECT * FROM tickets WHERE 1=1"
            params = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if category:
                query += " AND category = ?"
                params.append(category)
            if building:
                query += " AND building = ?"
                params.append(building)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def update_ticket_status(self, ticket_id: str, new_status: str, actor_id: str,
                             assigned_to: Optional[str] = None, details: Optional[str] = None) -> bool:
        valid_transitions = {
            "Submitted": ["Acknowledged", "Rejected", "Duplicate"],
            "Acknowledged": ["Assigned", "Rejected"],
            "Assigned": ["In Progress", "Rejected"],
            "In Progress": ["Resolved", "Rejected"],
            "Resolved": ["Closed", "Reopened"],
            "Closed": ["Reopened"],
            "Rejected": [],
            "Duplicate": [],
            "Reopened": ["Assigned", "In Progress", "Rejected"],
        }
        with self.get_connection() as conn:
            current = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            if not current:
                return False
            current_status = current["status"]
            if new_status not in valid_transitions.get(current_status, []):
                return False

            now = datetime.now(timezone.utc).isoformat()
            updates = ["status = ?", "updated_at = ?"]
            params = [new_status, now]
            if assigned_to is not None:
                updates.append("assigned_to = ?")
                params.append(assigned_to)
            params.append(ticket_id)
            conn.execute(f"UPDATE tickets SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
        self.log_ticket_history(ticket_id, actor_id, f"status_changed:{new_status}", details or "")
        return True

    def add_ticket_note(self, ticket_id: str, actor_id: str, note: str, is_internal: bool = True) -> bool:
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE tickets SET updated_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), ticket_id)
            )
            conn.commit()
        self.log_ticket_history(ticket_id, actor_id, "note_added", note, is_internal)
        return True

    # ==============================================================
    # Campus Issues — Ticket History
    # ==============================================================
    def log_ticket_history(self, ticket_id: str, actor_id: str, action: str,
                           details: str = "", is_internal: bool = True) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO ticket_history (ticket_id, actor_id, action, details, timestamp) VALUES (?, ?, ?, ?, ?)",
                (ticket_id, actor_id, action, details, now)
            )
            conn.commit()
            return cursor.lastrowid

    def get_ticket_history(self, ticket_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT th.*, u.username, u.role FROM ticket_history th JOIN users u ON th.actor_id = u.id WHERE th.ticket_id = ? ORDER BY th.timestamp",
                (ticket_id,)
            ).fetchall()
            return [dict(r) for r in rows]
