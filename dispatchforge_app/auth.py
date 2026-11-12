"""Workspace authentication and authorization for the prototype website."""
import hashlib
import hmac
import re
import secrets
from sqlalchemy import select
from sqlalchemy.orm import Session
from .errors import DomainError
from .inventory_service import clean_text, create_warehouse
from .models import Business, User


def hash_password(password: str) -> str:
    if not 10 <= len(password) <= 128:
        raise DomainError("Password must be between 10 and 128 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return f"pbkdf2_sha256$260000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, expected_hex = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or int(iterations) != 260_000:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                     bytes.fromhex(salt_hex), 260_000)
        return hmac.compare_digest(digest, bytes.fromhex(expected_hex))
    except (ValueError, TypeError):
        return False


def validate_email(value: str) -> str:
    value = (value or "").strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise DomainError("Provide a valid email address")
    return value


def register_business(session: Session, business_name: str, email: str,
                      password: str) -> tuple[Business, User]:
    name = clean_text(business_name, "Business name", 120)
    email = validate_email(email)
    # Display-friendly, unpredictable workspace slug avoids collisions.
    slug_base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:45] or "workspace"
    slug = f"{slug_base}-{secrets.token_hex(3)}"
    business = Business(name=name, slug=slug)
    session.add(business)
    session.flush()
    owner = User(business_id=business.id, email=email,
                 password_hash=hash_password(password), role="owner")
    session.add(owner)
    create_warehouse(session, business.id, "Main Warehouse", "Denton")
    session.flush()
    return business, owner


def authenticate(session: Session, workspace: str, email: str, password: str) -> User | None:
    business = session.scalar(select(Business).where(Business.slug == workspace.strip().lower()))
    if not business:
        return None
    user = session.scalar(select(User).where(User.business_id == business.id,
                                            User.email == email.strip().lower()))
    if user and user.role != "disabled" and verify_password(password, user.password_hash):
        return user
    return None


def actor_from_session(session: Session, signed_session: dict) -> User | None:
    uid = signed_session.get("uid")
    bid = signed_session.get("bid")
    if not isinstance(uid, int) or not isinstance(bid, int):
        return None
    return session.scalar(select(User).where(User.id == uid, User.business_id == bid,
                                           User.role != "disabled"))


def require_role(user: User | None, allowed: set[str]) -> None:
    if user is None:
        raise DomainError("Sign in to continue", 401)
    if user.role not in allowed:
        raise DomainError("Your account is not permitted to perform this action", 403)


def csrf_token(request) -> str:
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_urlsafe(32)
    return request.session["csrf"]


def check_csrf(request, supplied: str) -> None:
    saved = request.session.get("csrf", "")
    if not saved or not supplied or not hmac.compare_digest(saved, supplied):
        raise DomainError("Security token expired. Refresh the page and try again.", 403)
