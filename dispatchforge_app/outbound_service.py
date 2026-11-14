"""Order-bound scan picking / packing / dispatch.

StockLevel remains the accounting authority. A planned pick reserves BinStock,
a verified pick moves those units to staged stock without reducing StockLevel,
and dispatch issues the goods once, atomically with releasing the order reserve.
"""
import hashlib
import json
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .errors import DomainError
from .models import (BinStock, CustomerOrder, OrderLine, OutboundPick, OutboundPickEvent,
                     Product, StockLevel, WarehouseBin, utcnow)
from .warehouse_execution import KEY, _stock_guard

ACTIVE_PICK = ("queued", "assigned", "in_progress")
STAGED_PICK = ("picked", "packed")


def _fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _valid_key(value: str):
    if not isinstance(value, str) or not KEY.fullmatch(value):
        raise DomainError("Idempotency-Key required (8–128 safe characters)")


def _order(session: Session, bid: int, order_id: int) -> CustomerOrder:
    order = session.scalar(select(CustomerOrder).where(
        CustomerOrder.business_id == bid, CustomerOrder.id == order_id))
    if order is None:
        raise DomainError("Order not found", 404)
    return order


def _pick(session: Session, bid: int, pick_id: int) -> OutboundPick:
    row = session.scalar(select(OutboundPick).where(
        OutboundPick.business_id == bid, OutboundPick.id == pick_id))
    if row is None:
        raise DomainError("Outbound pick not found", 404)
    return row


def _event(session: Session, pick: OutboundPick, actor_id: int, action: str, detail: str = ""):
    session.add(OutboundPickEvent(business_id=pick.business_id, pick_id=pick.id,
        actor_id=actor_id, action=action, detail=detail[:250]))


def _insert_stmt(session: Session, model):
    return pg_insert(model) if session.get_bind().dialect.name == 'postgresql' else sqlite_insert(model)


def plan_pick(session: Session, bid: int, order_id: int, order_line_id: int,
              bin_id: int, quantity: int, actor_id: int, key: str):
    """Reserve real bin units for exactly one order line; safe under concurrent operators."""
    _valid_key(key)
    if type(quantity) is not int or not 1 <= quantity <= 1_000_000:
        raise DomainError("Pick quantity must be between 1 and 1,000,000")
    norm = dict(order_id=order_id, order_line_id=order_line_id, bin_id=bin_id, quantity=quantity)
    fingerprint = _fingerprint(norm)
    prev = session.scalar(select(OutboundPick).where(
        OutboundPick.business_id == bid, OutboundPick.idempotency_key == key))
    if prev:
        if prev.request_fingerprint != fingerprint:
            raise DomainError("Idempotency key reused with different pick details", 409)
        return prev, True
    order = _order(session, bid, order_id)
    if order.status != 'reserved':
        raise DomainError("Only reserved orders can be picked", 409)
    line = session.scalar(select(OrderLine).where(OrderLine.id == order_line_id,
        OrderLine.order_id == order.id, OrderLine.business_id == bid))
    if line is None:
        raise DomainError("Order line does not belong to this order", 404)
    _stock_guard(session, bid, order.warehouse_id, line.product_id)
    # Recheck both idempotency and order state AFTER acquiring the SKU lock.
    session.refresh(order)
    if order.status != 'reserved':
        raise DomainError("Order is no longer reserved", 409)
    prev = session.scalar(select(OutboundPick).where(
        OutboundPick.business_id == bid, OutboundPick.idempotency_key == key))
    if prev:
        if prev.request_fingerprint != fingerprint:
            raise DomainError("Idempotency key reused with different pick details", 409)
        return prev, True
    bin_row = session.scalar(select(WarehouseBin).where(WarehouseBin.business_id == bid,
        WarehouseBin.warehouse_id == order.warehouse_id, WarehouseBin.id == bin_id,
        WarehouseBin.active.is_(True)))
    if bin_row is None:
        raise DomainError("Active source bin not found in this warehouse", 404)
    allocated_to_order = session.scalar(select(func.coalesce(func.sum(OutboundPick.quantity), 0))
        .where(OutboundPick.business_id == bid, OutboundPick.order_line_id == line.id,
               OutboundPick.status != 'canceled'))
    if allocated_to_order + quantity > line.quantity:
        raise DomainError("Pick plans exceed reserved order line quantity", 409)
    inserted = session.scalar(_insert_stmt(session, OutboundPick).values(
        business_id=bid, order_id=order.id, order_line_id=line.id,
        warehouse_id=order.warehouse_id, product_id=line.product_id,
        bin_id=bin_id, quantity=quantity, status='queued', created_by=actor_id,
        idempotency_key=key, request_fingerprint=fingerprint, created_at=utcnow()
    ).on_conflict_do_nothing(index_elements=['business_id', 'idempotency_key'])
        .returning(OutboundPick.id))
    if inserted is None:
        prev = session.scalar(select(OutboundPick).where(
            OutboundPick.business_id == bid, OutboundPick.idempotency_key == key))
        if prev is None or prev.request_fingerprint != fingerprint:
            raise DomainError("Idempotency key conflicts with another pick", 409)
        return prev, True
    # Conditional write prevents overbooking against warehouse moves and other picks.
    result = session.execute(update(BinStock).where(BinStock.business_id == bid,
        BinStock.warehouse_id == order.warehouse_id, BinStock.bin_id == bin_id,
        BinStock.product_id == line.product_id,
        BinStock.on_hand - BinStock.allocated >= quantity
    ).values(allocated=BinStock.allocated + quantity))
    if result.rowcount != 1:
        raise DomainError("Not enough uncommitted stock at the selected bin", 409)
    pick = session.get(OutboundPick, inserted)
    _event(session, pick, actor_id, 'planned', f"Bin {bin_row.code}; {quantity} units")
    session.flush()
    return pick, False


def list_picks(session: Session, bid: int, order_id: int | None = None) -> list[dict]:
    q = (select(OutboundPick, Product.sku, WarehouseBin.code)
         .join(Product, Product.id == OutboundPick.product_id)
         .join(WarehouseBin, WarehouseBin.id == OutboundPick.bin_id)
         .where(OutboundPick.business_id == bid, Product.business_id == bid,
                WarehouseBin.business_id == bid))
    if order_id is not None:
        _order(session, bid, order_id)
        q = q.where(OutboundPick.order_id == order_id)
    return [{'id': p.id, 'order_id': p.order_id, 'order_line_id': p.order_line_id,
             'warehouse_id': p.warehouse_id, 'bin_id': p.bin_id,
             'bin_code': bin_code, 'sku': sku, 'quantity': p.quantity,
             'status': p.status, 'assigned_user_id': p.assigned_user_id,
             'picked_by': p.picked_by, 'created_at': p.created_at.isoformat()}
            for p, sku, bin_code in session.execute(q.order_by(OutboundPick.id.desc()).limit(200))]


def pick_events(session: Session, bid: int, pick_id: int):
    _pick(session, bid, pick_id)
    return [{'action': e.action, 'actor_id': e.actor_id, 'detail': e.detail,
             'created_at': e.created_at.isoformat()} for e in session.scalars(
        select(OutboundPickEvent).where(OutboundPickEvent.business_id == bid,
            OutboundPickEvent.pick_id == pick_id).order_by(OutboundPickEvent.id))]
