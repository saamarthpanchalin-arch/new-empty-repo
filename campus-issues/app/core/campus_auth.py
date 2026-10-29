import hashlib
import secrets
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from itsdangerous import TimestampSigner, BadSignature, SignatureExpired
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# Use pbkdf2_sha256 which works reliably on Python 3.14
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

@dataclass
class Session:
    user_id: str
    username: str
    role: str
    created_at: str
    expires_at: str

class CampusAuthManager:
    """Manages user authentication and sessions for Campus Issues."""

    def __init__(self, sqlite_store, secret_key: str):
        self.sqlite = sqlite_store
        self.signer = TimestampSigner(secret_key)
        self.session_duration = timedelta(days=30)

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def create_session(self, user: Dict[str, Any]) -> str:
        """Create a signed session cookie."""
        payload = f"{user['id']}|{user['username']}|{user['role']}"
        return self.signer.sign(payload.encode()).decode()

    def verify_session(self, session_cookie: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a session cookie."""
        try:
            payload = self.signer.unsign(session_cookie.encode(), max_age=int(self.session_duration.total_seconds())).decode()
            user_id, username, role = payload.split("|")
            return {"user_id": user_id, "username": username, "role": role}
        except (BadSignature, SignatureExpired, ValueError):
            return None

    def register_user(self, username: str, email: str, password: str, role: str = "student") -> Optional[Dict[str, Any]]:
        """Register a new user. Returns user dict or None if email/username exists."""
        if self.sqlite.get_user_by_email(email):
            return None
        if self.sqlite.get_user_by_username(username):
            return None

        user_id = f"usr_{secrets.token_urlsafe(16)}"
        password_hash = self.hash_password(password)

        user = self.sqlite.create_user(user_id, username, email, password_hash, role)
        logger.info(f"Registered user {username} ({role})")
        return user

    def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with email and password. Returns user dict if valid."""
        user = self.sqlite.get_user_by_email(email)
        if not user:
            return None
        if not self.verify_password(password, user["password_hash"]):
            return None
        return user