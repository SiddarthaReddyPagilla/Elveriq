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

def create_notice(session: Session, bid: int, po_id: int, reference: str,
                  supplier_reference: str, dock: str, items: list[dict], actor_id: int):
    """Plan outstanding PO quantities; never create stock from a supplier manifest."""
    reference = (reference or '').strip().upper()
    supplier_reference = (supplier_reference or '').strip()
    dock = (dock or '').strip().upper()
    if not 1 <= len(reference) <= 100 or len(supplier_reference) > 120 or len(dock) > 64:
        raise DomainError('Invalid ASN reference, supplier reference, or dock')
    if not 1 <= len(items) <= 100:
        raise DomainError('ASN requires 1–100 purchase order lines')
    po = session.scalar(select(PurchaseOrder).where(PurchaseOrder.business_id == bid,
        PurchaseOrder.id == po_id).with_for_update())
    if po is None:
        raise DomainError('Purchase order not found', 404)
    if po.status not in ('ordered', 'partial'):
        raise DomainError('Purchase order no longer accepts inbound notices', 409)
    if session.scalar(select(InboundNotice.id).where(InboundNotice.business_id == bid,
            InboundNotice.reference == reference)):
        raise DomainError('Inbound reference already exists', 409)
    seen = set()
    planned = []
    for item in items:
        line_id, quantity = item['purchase_line_id'], item['expected']
        if line_id in seen or type(quantity) is not int or not 1 <= quantity <= 1_000_000:
            raise DomainError('Repeated PO line or invalid ASN quantity')
        seen.add(line_id)
        line = session.scalar(select(PurchaseOrderLine).where(PurchaseOrderLine.id == line_id,
            PurchaseOrderLine.purchase_order_id == po_id,
            PurchaseOrderLine.business_id == bid).with_for_update())
        if line is None:
            raise DomainError('ASN line must belong to this purchase order', 404)
        active = session.scalar(select(func.coalesce(func.sum(InboundNoticeLine.expected),0))
            .join(InboundNotice, InboundNotice.id == InboundNoticeLine.notice_id)
            .where(InboundNotice.business_id == bid,
                InboundNotice.purchase_order_id == po_id,
                InboundNotice.status.in_(('planned','arrived')),
                InboundNoticeLine.purchase_line_id == line_id))
        if quantity + active > line.ordered_quantity - line.received_quantity:
            raise DomainError('ASN quantities exceed unreceived, unplanned PO stock', 409)
        planned.append((line_id, quantity))
    notice = InboundNotice(business_id=bid, purchase_order_id=po_id,
        warehouse_id=po.warehouse_id, reference=reference,
        supplier_reference=supplier_reference, dock=dock, created_by=actor_id)
    session.add(notice)
    session.flush()
    for line_id, qty in planned:
        session.add(InboundNoticeLine(business_id=bid, notice_id=notice.id,
            purchase_line_id=line_id, expected=qty, accepted=0, damaged=0))
    _event(session, notice, actor_id, 'planned', f'{len(items)} PO lines')
    session.flush()
    return notice

def arrive_notice(session: Session, bid: int, notice_id: int, actor_id: int):
    notice = _notice(session, bid, notice_id, lock=True)
    if notice.status == 'arrived':
        return notice, True
    if notice.status != 'planned':
        raise DomainError('Only planned ASNs can arrive', 409)
    if session.execute(update(InboundNotice).where(InboundNotice.id == notice_id,
        InboundNotice.business_id == bid, InboundNotice.status == 'planned')
        .values(status='arrived', arrived_by=actor_id, arrived_at=utcnow())).rowcount != 1:
        raise DomainError('ASN arrival state changed', 409)
    _event(session, notice, actor_id, 'arrived', f'Dock {notice.dock or "unassigned"}')
    session.refresh(notice)
    return notice, False
