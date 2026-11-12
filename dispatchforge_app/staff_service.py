"""Workspace staff invitations and account management.

No email delivery integration yet. Invite token must be shared securely by owner.
"""
from datetime import timedelta, timezone
import hashlib
import secrets
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .auth import hash_password, validate_email
from .errors import DomainError
from .models import StaffInvitation, User, utcnow


def create_invitation(session: Session, business_id: int, email: str,
                      role: str, actor_id: int) -> tuple[StaffInvitation, str]:
    email = validate_email(email)
    if role not in {'manager', 'staff'}:
        raise DomainError('Invitations support only manager or staff roles')
    if session.scalar(select(User.id).where(
        User.business_id == business_id, User.email == email)):
        raise DomainError('Staff account already exists', 409)
    token = secrets.token_urlsafe(32)
    invitation = StaffInvitation(business_id=business_id, email=email, role=role,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=utcnow()+timedelta(hours=48), created_by=actor_id)
    session.add(invitation)
    session.flush()
    return invitation, token


def accept_invitation(session: Session, token: str, password: str) -> User:
    if not isinstance(token, str) or len(token) > 200 or len(token) < 20:
        raise DomainError('Invitation is invalid or expired', 400)
    digest = hashlib.sha256(token.encode()).hexdigest()
    invite = session.scalar(select(StaffInvitation).where(
        StaffInvitation.token_hash == digest).with_for_update())
    if invite is None or invite.accepted_at is not None:
        raise DomainError('Invitation is invalid or already used', 400)
    expiry = invite.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= utcnow():
        raise DomainError('Invitation expired', 400)
    # Validate/hash the password before claiming the invitation.
    password_hash = hash_password(password)
    if session.scalar(select(User.id).where(
        User.business_id == invite.business_id, User.email == invite.email)):
        raise DomainError('Staff account already exists', 409)
    result = session.execute(update(StaffInvitation).where(
        StaffInvitation.id == invite.id, StaffInvitation.accepted_at.is_(None))
        .values(accepted_at=utcnow()))
    if result.rowcount != 1:
        raise DomainError('Invitation has already been used', 409)
    user = User(business_id=invite.business_id, email=invite.email,
        role=invite.role, password_hash=password_hash)
    session.add(user)
    session.flush()
    return user


def staff_members(session: Session, business_id: int) -> list[dict]:
    users = session.scalars(select(User).where(User.business_id == business_id)
        .order_by(User.id)).all()
    return [{"id": u.id, "email": u.email, "role": u.role,
             "created_at": u.created_at.isoformat()} for u in users]


def change_staff_role(session: Session, business_id: int, user_id: int,
                      role: str, owner_id: int) -> User:
    if role not in {'manager','staff','disabled'}:
        raise DomainError('Allowed roles are manager, staff or disabled')
    user = session.scalar(select(User).where(User.business_id == business_id,
                                             User.id == user_id))
    if user is None:
        raise DomainError('Employee not found', 404)
    if user.role == 'owner' or user.id == owner_id:
        raise DomainError('Owner account cannot be changed through staff management', 403)
    user.role = role
    session.flush()
    return user
