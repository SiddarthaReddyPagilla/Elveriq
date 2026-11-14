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
                     Product, StockLevel, WarehouseBin, OutboundCarton, OutboundCartonItem, utcnow)
from .warehouse_execution import KEY, _stock_guard, code

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


def claim_pick(session: Session, bid: int, pick_id: int, actor_id: int):
    pick = _pick(session, bid, pick_id)
    _stock_guard(session, bid, pick.warehouse_id, pick.product_id)
    result = session.execute(update(OutboundPick).where(OutboundPick.id == pick_id,
        OutboundPick.business_id == bid, OutboundPick.status == 'queued',
        OutboundPick.assigned_user_id.is_(None)
    ).values(status='assigned', assigned_user_id=actor_id))
    if result.rowcount != 1:
        raise DomainError("Pick already claimed or closed", 409)
    session.refresh(pick)
    _event(session, pick, actor_id, 'claimed')
    session.flush()
    return pick


def start_pick(session: Session, bid: int, pick_id: int, actor_id: int):
    pick = _pick(session, bid, pick_id)
    _stock_guard(session, bid, pick.warehouse_id, pick.product_id)
    result = session.execute(update(OutboundPick).where(OutboundPick.id == pick_id,
        OutboundPick.business_id == bid, OutboundPick.status == 'assigned',
        OutboundPick.assigned_user_id == actor_id
    ).values(status='in_progress'))
    if result.rowcount != 1:
        raise DomainError("Only the assigned picker can start this task", 409)
    session.refresh(pick)
    _event(session, pick, actor_id, 'started')
    session.flush()
    return pick


def cancel_pick(session: Session, bid: int, pick_id: int, actor_id: int):
    pick = _pick(session, bid, pick_id)
    _stock_guard(session, bid, pick.warehouse_id, pick.product_id)
    session.refresh(pick)
    if pick.status not in ACTIVE_PICK:
        raise DomainError("Only unpicked work can be canceled", 409)
    result = session.execute(update(BinStock).where(
        BinStock.business_id == bid, BinStock.warehouse_id == pick.warehouse_id,
        BinStock.bin_id == pick.bin_id, BinStock.product_id == pick.product_id,
        BinStock.allocated >= pick.quantity
    ).values(allocated=BinStock.allocated - pick.quantity))
    if result.rowcount != 1:
        raise DomainError("Source bin commitment could not be released", 409)
    pick.status = 'canceled'
    _event(session, pick, actor_id, 'canceled')
    session.flush()
    return pick


def scan_pick(session: Session, bid: int, pick_id: int, actor_id: int,
              scan_sku: str, scan_bin: str):
    """Physical removal is atomic with the pick event; accounting stays reserved."""
    pick = _pick(session, bid, pick_id)
    _stock_guard(session, bid, pick.warehouse_id, pick.product_id)
    session.refresh(pick)
    scans = {'sku': (scan_sku or '').strip().upper(),
             'bin': (scan_bin or '').strip().upper()}
    fingerprint = _fingerprint(scans)
    if pick.status in ('picked', 'packed', 'shipped'):
        if pick.picked_by == actor_id and pick.scan_fingerprint == fingerprint:
            return pick, True
        raise DomainError("Pick already verified by another worker or scan", 409)
    if pick.status != 'in_progress' or pick.assigned_user_id != actor_id:
        raise DomainError("Only the assigned active picker can confirm", 409)
    product = session.scalar(select(Product).where(Product.id == pick.product_id,
        Product.business_id == bid))
    bin_row = session.scalar(select(WarehouseBin).where(WarehouseBin.id == pick.bin_id,
        WarehouseBin.business_id == bid, WarehouseBin.warehouse_id == pick.warehouse_id))
    if bin_row is None or not bin_row.active:
        raise DomainError("Source bin is blocked", 409)
    if scans['sku'] != product.sku or scans['bin'] != bin_row.code:
        _event(session, pick, actor_id, 'scan_rejected', 'SKU/bin verification mismatch')
        session.flush()
        raise DomainError("Outbound scan verification failed: check SKU and source bin", 409)
    result = session.execute(update(BinStock).where(
        BinStock.business_id == bid, BinStock.warehouse_id == pick.warehouse_id,
        BinStock.bin_id == pick.bin_id, BinStock.product_id == pick.product_id,
        BinStock.on_hand >= pick.quantity, BinStock.allocated >= pick.quantity
    ).values(on_hand=BinStock.on_hand - pick.quantity,
             allocated=BinStock.allocated - pick.quantity))
    if result.rowcount != 1:
        raise DomainError("Planned bin stock is no longer available", 409)
    pick.status = 'picked'
    pick.picked_by = actor_id
    pick.scan_fingerprint = fingerprint
    pick.picked_at = utcnow()
    _event(session, pick, actor_id, 'picked', f'Scanned {product.sku} at {bin_row.code}')
    session.flush()
    return pick, False


def _carton(session: Session, bid: int, carton_id: int):
    carton = session.scalar(select(OutboundCarton).where(
        OutboundCarton.business_id == bid, OutboundCarton.id == carton_id))
    if carton is None:
        raise DomainError("Carton not found", 404)
    return carton


def create_carton(session: Session, bid: int, order_id: int, carton_code: str, actor_id: int):
    order = _order(session, bid, order_id)
    if order.status != 'reserved':
        raise DomainError("Cartons require a reserved order", 409)
    carton_code = code(carton_code)
    if session.scalar(select(OutboundCarton.id).where(
            OutboundCarton.business_id == bid, OutboundCarton.code == carton_code)):
        raise DomainError("Carton code already exists in this workspace", 409)
    carton = OutboundCarton(business_id=bid, order_id=order.id,
        warehouse_id=order.warehouse_id, code=carton_code,
        status='open', created_by=actor_id)
    session.add(carton)
    session.flush()
    return carton


def pack_pick(session: Session, bid: int, carton_id: int, pick_id: int,
              actor_id: int, scan_sku: str, scan_carton: str):
    pick = _pick(session, bid, pick_id)
    _stock_guard(session, bid, pick.warehouse_id, pick.product_id)
    session.refresh(pick)
    carton = _carton(session, bid, carton_id)
    session.refresh(carton)
    product = session.scalar(select(Product).where(Product.id == pick.product_id,
        Product.business_id == bid))
    if (scan_sku or '').strip().upper() != product.sku or \
            (scan_carton or '').strip().upper() != carton.code:
        _event(session, pick, actor_id, 'pack_scan_rejected', 'SKU/carton verification mismatch')
        session.flush()
        raise DomainError("Packing scan verification failed: check SKU and carton", 409)
    if pick.order_id != carton.order_id or pick.warehouse_id != carton.warehouse_id:
        raise DomainError("Pick and carton belong to different orders or warehouses", 409)
    if pick.status == 'packed':
        item = session.scalar(select(OutboundCartonItem).where(
            OutboundCartonItem.business_id == bid, OutboundCartonItem.pick_id == pick.id,
            OutboundCartonItem.carton_id == carton.id))
        if item:
            return pick, True
        raise DomainError("Pick already packed into another carton", 409)
    if carton.status != 'open':
        raise DomainError("Carton already sealed or dispatched", 409)
    result = session.execute(update(OutboundPick).where(OutboundPick.business_id == bid,
        OutboundPick.id == pick.id, OutboundPick.status == 'picked'
    ).values(status='packed'))
    if result.rowcount != 1:
        raise DomainError("Only a verified, unpacked pick can be packed", 409)
    session.add(OutboundCartonItem(business_id=bid, carton_id=carton.id,
        pick_id=pick.id, quantity=pick.quantity, packed_by=actor_id))
    _event(session, pick, actor_id, 'packed', f'Carton {carton.code}')
    session.flush()
    session.refresh(pick)
    return pick, False


def seal_carton(session: Session, bid: int, carton_id: int, actor_id: int):
    carton = _carton(session, bid, carton_id)
    # Conditional status transition serializes sealing with other packers.
    count = session.scalar(select(func.count(OutboundCartonItem.id)).where(
        OutboundCartonItem.business_id == bid, OutboundCartonItem.carton_id == carton.id))
    if not count:
        raise DomainError("Cannot seal an empty carton", 409)
    result = session.execute(update(OutboundCarton).where(
        OutboundCarton.id == carton.id, OutboundCarton.business_id == bid,
        OutboundCarton.status == 'open').values(
            status='sealed', sealed_by=actor_id, sealed_at=utcnow()))
    if result.rowcount != 1:
        raise DomainError("Carton is already sealed or shipped", 409)
    session.refresh(carton)
    return carton


def list_cartons(session: Session, bid: int, order_id: int | None = None):
    q = select(OutboundCarton).where(OutboundCarton.business_id == bid)
    if order_id is not None:
        _order(session, bid, order_id)
        q = q.where(OutboundCarton.order_id == order_id)
    cartons = session.scalars(q.order_by(OutboundCarton.id.desc()).limit(200)).all()
    result = []
    for carton in cartons:
        items = session.execute(select(OutboundCartonItem, OutboundPick, Product.sku)
            .join(OutboundPick, OutboundPick.id == OutboundCartonItem.pick_id)
            .join(Product, Product.id == OutboundPick.product_id)
            .where(OutboundCartonItem.business_id == bid,
                   OutboundCartonItem.carton_id == carton.id)).all()
        result.append({'id': carton.id, 'order_id': carton.order_id,
            'code': carton.code, 'status': carton.status,
            'items': [{'pick_id': p.id, 'sku': sku, 'quantity': item.quantity}
                      for item,p,sku in items]})
    return result
