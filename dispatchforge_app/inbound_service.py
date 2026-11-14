"""PO-linked inbound ASN workflows with atomic receipt posting and retry-safe scans."""
import hashlib
import json
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
from .errors import DomainError
from .models import (InboundNotice, InboundNoticeLine, InboundReceipt, InboundNoticeEvent,
    PurchaseOrder, PurchaseOrderLine, Product, utcnow)
from .purchasing_service import receive_purchase_line
from .warehouse_execution import KEY


def _notice(session: Session, bid: int, notice_id: int, lock: bool = False):
    q = select(InboundNotice).where(InboundNotice.id == notice_id, InboundNotice.business_id == bid)
    notice = session.scalar(q.with_for_update() if lock else q)
    if notice is None:
        raise DomainError("Inbound notice not found", 404)
    return notice


def _event(session: Session, notice: InboundNotice, actor_id: int, action: str, note: str = ""):
    session.add(InboundNoticeEvent(business_id=notice.business_id, notice_id=notice.id,
        actor_id=actor_id, action=action, note=note[:250]))


def _fingerprint(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',', ':')).encode()).hexdigest()


def _key(value):
    if not isinstance(value, str) or not KEY.fullmatch(value):
        raise DomainError("Idempotency-Key required (8–128 safe characters)")


def _insert(session, model):
    return pg_insert(model) if session.get_bind().dialect.name == 'postgresql' else sqlite_insert(model)
