import hashlib
import secrets
import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

@dataclass
class APIKey:
    """Represents an API key with metadata."""
    key_id: str
    key_hash: str
    name: str
    application_id: str
    created_at: str
    last_used_at: Optional[str] = None
    revoked: bool = False
    scopes: Optional[list] = None  # e.g., ["read", "write", "admin"]

class AuthManager:
    """Manages API key authentication and authorization."""
    
    def __init__(self, sqlite_store):
        self.sqlite = sqlite_store
        self._init_tables()
    
    def _init_tables(self):
        """Create API key tables if they don't exist."""
        with self.sqlite.get_connection() as conn:
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
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
            """)
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_keys_app ON api_keys(application_id);
            """)
            conn.commit()
    
    def hash_key(self, key: str) -> str:
        """Hash an API key using SHA-256."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def generate_key(self) -> str:
        """Generate a new cryptographically secure API key."""
        return f"rag_{secrets.token_urlsafe(32)}"
    
    def create_key(
        self,
        application_id: str,
        name: str,
        scopes: Optional[list] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """Create a new API key for an application."""
        # Verify application exists
        app = self.sqlite.get_application(application_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        
        key = self.generate_key()
        key_id = f"key_{secrets.token_urlsafe(16)}"
        key_hash = self.hash_key(key)
        scopes = scopes or ["read", "write"]
        
        now = datetime.now(timezone.utc).isoformat()
        
        with self.sqlite.get_connection() as conn:
            conn.execute(
                """INSERT INTO api_keys 
                (key_id, key_hash, name, application_id, scopes_json, created_at, revoked)
                VALUES (?, ?, ?, ?, ?, ?, FALSE)""",
                (key_id, key_hash, name, application_id, json.dumps(scopes), now)
            )
            conn.commit()
        
        key_info = {
            "key_id": key_id,
            "name": name,
            "application_id": application_id,
            "scopes": scopes,
            "created_at": now,
            "revoked": False,
        }
        
        logger.info(f"Created API key {key_id} for application {application_id}")
        self.sqlite.log_audit(application_id, "api_key_created", {
            "key_id": key_id,
            "name": name,
            "scopes": scopes,
        })
        return key, key_info
    
    def verify_key(self, key: str) -> Optional[Dict[str, Any]]:
        """Verify an API key and return key info if valid."""
        key_hash = self.hash_key(key)
        
        with self.sqlite.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM api_keys WHERE key_hash = ? AND revoked = FALSE",
                (key_hash,)
            ).fetchone()
            
            if not row:
                return None
            
            key_info = dict(row)
            key_info['scopes'] = json.loads(key_info['scopes_json'])
            
            # Update last_used_at
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE key_id = ?",
                (now, key_info['key_id'])
            )
            conn.commit()
            
            return key_info
    
    def revoke_key(self, key_id: str, application_id: str) -> bool:
        """Revoke an API key."""
        with self.sqlite.get_connection() as conn:
            result = conn.execute(
                "UPDATE api_keys SET revoked = TRUE WHERE key_id = ? AND application_id = ?",
                (key_id, application_id)
            )
            conn.commit()
            revoked = result.rowcount > 0
        
        if revoked:
            self.sqlite.log_audit(application_id, "api_key_revoked", {
                "key_id": key_id,
            })
        return revoked
    
    def list_keys(self, application_id: str) -> list[Dict[str, Any]]:
        """List all API keys for an application (excluding hashes)."""
        with self.sqlite.get_connection() as conn:
            rows = conn.execute(
                "SELECT key_id, name, application_id, scopes_json, created_at, last_used_at, revoked FROM api_keys WHERE application_id = ? ORDER BY created_at DESC",
                (application_id,)
            ).fetchall()
            
            keys = []
            for row in rows:
                key_info = dict(row)
                key_info['scopes'] = json.loads(key_info['scopes_json'])
                del key_info['scopes_json']
                keys.append(key_info)
            return keys

# FastAPI dependency for authentication
security = HTTPBearer(auto_error=False)

def get_auth_manager(request: Request) -> AuthManager:
    """Dependency to get auth manager from app state."""
    return request.app.state.auth_manager

async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_manager: AuthManager = Depends(get_auth_manager),
    required_scopes: Optional[list] = None,
) -> Dict[str, Any]:
    """FastAPI dependency that requires valid API key authentication."""
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    key_info = auth_manager.verify_key(credentials.credentials)
    if not key_info:
        raise HTTPException(
            status_code=401,
            detail="Invalid or revoked API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check required scopes
    if required_scopes:
        key_scopes = key_info.get('scopes', [])
        if not all(scope in key_scopes for scope in required_scopes):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required scopes: {required_scopes}"
            )
    
    return key_info

def require_scopes(*scopes: str):
    """Create a dependency that requires specific scopes."""
    async def check_scopes(
        key_info: Dict[str, Any] = Depends(require_auth),
    ) -> Dict[str, Any]:
        key_scopes = key_info.get('scopes', [])
        if not all(scope in key_scopes for scope in scopes):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required scopes: {list(scopes)}"
            )
        return key_info
    return check_scopes