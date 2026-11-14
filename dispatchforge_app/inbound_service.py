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

def scan_receipt(session: Session, bid: int, notice_id: int, notice_line_id: int,
                 sku: str, accepted: int, damaged: int, damage_note: str, actor_id: int, key: str):
    """One atomic disposition, purchase receipt and stock movement per unique scan key."""
    _key(key)
    sku = (sku or '').strip().upper()
    damage_note = (damage_note or '').strip()
    if type(accepted) is not int or type(damaged) is not int or min(accepted, damaged) < 0 or        accepted + damaged < 1 or accepted + damaged > 1_000_000:
        raise DomainError('Scan must accept or mark damaged at least one unit')
    if damaged and not (3 <= len(damage_note) <= 250):
        raise DomainError('Damaged receipt requires a 3–250 character reason')
    if len(damage_note) > 250:
        raise DomainError('Damage note too long')
    details = dict(notice_id=notice_id, notice_line_id=notice_line_id,
        sku=sku, accepted=accepted, damaged=damaged, damage_note=damage_note)
    fingerprint = _fingerprint(details)
    prev = session.scalar(select(InboundReceipt).where(InboundReceipt.business_id == bid,
        InboundReceipt.idempotency_key == key))
    if prev:
        if prev.request_fingerprint != fingerprint:
            raise DomainError('Idempotency key reused for different receipt details', 409)
        return prev, True
    notice = _notice(session, bid, notice_id, lock=True)
    if notice.status != 'arrived':
        raise DomainError('ASN must be arrived before scanning receipts', 409)
    line = session.scalar(select(InboundNoticeLine).where(
        InboundNoticeLine.business_id == bid, InboundNoticeLine.notice_id == notice.id,
        InboundNoticeLine.id == notice_line_id).with_for_update())
    if line is None:
        raise DomainError('Inbound notice line not found', 404)
    po_line = session.scalar(select(PurchaseOrderLine).where(PurchaseOrderLine.id == line.purchase_line_id,
        PurchaseOrderLine.business_id == bid,
        PurchaseOrderLine.purchase_order_id == notice.purchase_order_id).with_for_update())
    product = session.scalar(select(Product).where(Product.id == po_line.product_id,
        Product.business_id == bid))
    if sku != product.sku:
        raise DomainError('Scanned SKU does not match expected purchase item', 409)
    prev = session.scalar(select(InboundReceipt).where(InboundReceipt.business_id == bid,
        InboundReceipt.idempotency_key == key))
    if prev:
        if prev.request_fingerprint != fingerprint:
            raise DomainError('Idempotency key reused for different receipt details', 409)
        return prev, True
    receipt_id = session.scalar(_insert(session, InboundReceipt).values(
        business_id=bid, notice_id=notice.id, notice_line_id=line.id,
        scan_sku=sku, accepted=accepted, damaged=damaged, damage_note=damage_note,
        idempotency_key=key, request_fingerprint=fingerprint,
        actor_id=actor_id, created_at=utcnow()
    ).on_conflict_do_nothing(index_elements=['business_id','idempotency_key'])
        .returning(InboundReceipt.id))
    if receipt_id is None:
        prev = session.scalar(select(InboundReceipt).where(InboundReceipt.business_id == bid,
            InboundReceipt.idempotency_key == key))
        if prev is None or prev.request_fingerprint != fingerprint:
            raise DomainError('Receipt retry key conflict', 409)
        return prev, True
    if session.execute(update(InboundNoticeLine).where(
        InboundNoticeLine.id == line.id, InboundNoticeLine.business_id == bid,
        InboundNoticeLine.accepted + InboundNoticeLine.damaged + accepted + damaged <= InboundNoticeLine.expected)
        .values(accepted=InboundNoticeLine.accepted + accepted,
                damaged=InboundNoticeLine.damaged + damaged)).rowcount != 1:
        raise DomainError('Scanned ASN quantities exceed expected units', 409)
    if accepted:
        receive_purchase_line(session, bid, notice.purchase_order_id,
                              po_line.id, accepted, actor_id)
    _event(session, notice, actor_id, 'receipt',
        f'{sku}: +{accepted} accepted, {damaged} damaged; receipt #{receipt_id}')
    session.flush()
    return session.get(InboundReceipt, receipt_id), False

def close_notice(session: Session, bid: int, notice_id: int, actor_id: int, note: str = ''):
    notice = _notice(session, bid, notice_id, lock=True)
    if notice.status != 'arrived':
        raise DomainError('Only arrived ASNs may be closed', 409)
    note = (note or '').strip()
    if len(note) > 250:
        raise DomainError('Closure note too long')
    lines = session.scalars(select(InboundNoticeLine).where(
        InboundNoticeLine.business_id == bid, InboundNoticeLine.notice_id == notice.id)).all()
    short = sum(line.expected-line.accepted-line.damaged for line in lines)
    if short and len(note) < 3:
        raise DomainError('A short shipment requires a closure reason', 409)
    if session.execute(update(InboundNotice).where(InboundNotice.id == notice.id,
        InboundNotice.business_id == bid, InboundNotice.status == 'arrived')
        .values(status='closed', closed_by=actor_id, closed_at=utcnow())).rowcount != 1:
        raise DomainError('Inbound notice closure state changed', 409)
    _event(session, notice, actor_id, 'closed', f'{short} units short; {note}'[:250])
    session.refresh(notice)
    return notice, short

def cancel_notice(session: Session, bid: int, notice_id: int, actor_id: int, note: str = ''):
    notice = _notice(session, bid, notice_id, lock=True)
    if notice.status not in ('planned', 'arrived'):
        raise DomainError('Only open ASNs can be canceled', 409)
    if session.scalar(select(InboundReceipt.id).where(InboundReceipt.business_id == bid,
        InboundReceipt.notice_id == notice.id).limit(1)):
        raise DomainError('An ASN with recorded dispositions cannot be canceled', 409)
    notice.status = 'canceled'
    _event(session, notice, actor_id, 'canceled', note)
    session.flush()
    return notice
