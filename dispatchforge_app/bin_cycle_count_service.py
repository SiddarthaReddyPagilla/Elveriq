"""Physical bin/SKU counts with owner-authorized reconciliation.

Warehouse aggregate StockLevel is the accounting authority, while BinStock is
physical placement. Posting adjusts both in one transaction and refuses stale
snapshots or active material-handling work for the counted location/SKU.
"""
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from .errors import DomainError
from .inventory_service import clean_text, get_stock
from .models import (BinCycleCount, BinStock, Product, StockLevel, StockMovement,
                     Warehouse, WarehouseBin, WarehouseTask, WarehouseTaskEvent, utcnow)
from .warehouse_execution import (ACTIVE, _bin, _capacity_check, _stock_guard,
                                  protected_units_expr)


def _active_work(session: Session, bid: int, bin_id: int, pid: int) -> bool:
    return session.scalar(select(WarehouseTask.id).where(
        WarehouseTask.business_id == bid,
        WarehouseTask.product_id == pid,
        WarehouseTask.status.in_(ACTIVE),
        or_(WarehouseTask.from_bin_id == bin_id, WarehouseTask.to_bin_id == bin_id)
    ).limit(1)) is not None


def _watermarks(session: Session, bid: int, wid: int, pid: int) -> tuple[int, int]:
    """Catch quantity ABA: intervening moves invalidate an open physical count
    even when they end up restoring its initial quantities.
    """
    latest_movement = session.scalar(select(func.coalesce(func.max(StockMovement.id), 0)).where(
        StockMovement.business_id == bid, StockMovement.warehouse_id == wid,
        StockMovement.product_id == pid))
    latest_task = session.scalar(select(func.coalesce(func.max(WarehouseTaskEvent.id), 0)).join(
        WarehouseTask, WarehouseTask.id == WarehouseTaskEvent.task_id).where(
        WarehouseTaskEvent.business_id == bid, WarehouseTask.business_id == bid,
        WarehouseTask.warehouse_id == wid, WarehouseTask.product_id == pid))
    return latest_movement, latest_task


def _record(session: Session, bid: int, count_id: int) -> BinCycleCount:
    result = session.scalar(select(BinCycleCount).where(
        BinCycleCount.id == count_id, BinCycleCount.business_id == bid))
    if result is None:
        raise DomainError('Bin cycle count not found', 404)
    return result


def start_bin_count(session: Session, bid: int, wid: int, bin_id: int,
                    sku: str, actor_id: int, note: str = '') -> BinCycleCount:
    if len(note or '') > 250:
        raise DomainError('Count note is too long')
    location = _bin(session, bid, wid, bin_id)
    product, _ = get_stock(session, bid, wid, clean_text(sku, 'SKU', 80).upper())
    stock = _stock_guard(session, bid, wid, product.id)
    if _active_work(session, bid, location.id, product.id):
        raise DomainError('Finish or cancel bin movement tasks before starting a count', 409)
    if session.scalar(select(BinCycleCount.id).where(
        BinCycleCount.business_id == bid, BinCycleCount.bin_id == bin_id,
        BinCycleCount.product_id == product.id, BinCycleCount.status == 'open')):
        raise DomainError('An open count already exists for this bin and SKU', 409)
    bin_stock = session.scalar(select(BinStock).where(
        BinStock.business_id == bid, BinStock.warehouse_id == wid,
        BinStock.bin_id == bin_id, BinStock.product_id == product.id))
    latest_movement, latest_task = _watermarks(session, bid, wid, product.id)
    count = BinCycleCount(
        business_id=bid, warehouse_id=wid, bin_id=bin_id, product_id=product.id,
        expected_on_hand=bin_stock.on_hand if bin_stock else 0,
        expected_allocated=bin_stock.allocated if bin_stock else 0,
        expected_warehouse_on_hand=stock.on_hand,
        expected_movement_id=latest_movement, expected_task_event_id=latest_task,
        note=(note or '').strip(), status='open', created_by=actor_id)
    session.add(count)
    session.flush()
    return count


def post_bin_count(session: Session, bid: int, count_id: int,
                   counted_on_hand: int, actor_id: int) -> BinCycleCount:
    if type(counted_on_hand) is not int or not 0 <= counted_on_hand <= 10_000_000:
        raise DomainError('Counted units must be between 0 and 10,000,000')
    count = _record(session, bid, count_id)
    if count.status != 'open':
        raise DomainError('Bin cycle count is already closed', 409)
    stock = _stock_guard(session, bid, count.warehouse_id, count.product_id)
    session.refresh(count)
    if count.status != 'open':
        raise DomainError('Bin cycle count is already closed', 409)
    location = _bin(session, bid, count.warehouse_id, count.bin_id)
    # Match other capacity writers: lock aggregate SKU then physical bin.
    session.scalar(select(WarehouseBin.id).where(
        WarehouseBin.id == count.bin_id, WarehouseBin.business_id == bid).with_for_update())
    if _active_work(session, bid, count.bin_id, count.product_id):
        raise DomainError('Finish or cancel bin movement tasks before reconciling', 409)
    current = session.scalar(select(BinStock).where(
        BinStock.business_id == bid, BinStock.warehouse_id == count.warehouse_id,
        BinStock.bin_id == count.bin_id, BinStock.product_id == count.product_id))
    old = current.on_hand if current else 0
    allocated = current.allocated if current else 0
    current_movement, current_task_event = _watermarks(
        session, bid, count.warehouse_id, count.product_id)
    if (stock.on_hand != count.expected_warehouse_on_hand
            or old != count.expected_on_hand
            or allocated != count.expected_allocated
            or current_movement != count.expected_movement_id
            or current_task_event != count.expected_task_event_id):
        raise DomainError('Stock changed since the count began; cancel and recount', 409)
    if counted_on_hand < allocated:
        raise DomainError('Counted units cannot be less than stock committed to tasks', 409)
    difference = counted_on_hand - old
    if difference > 0:
        if stock.on_hand + difference > 10_000_000:
            raise DomainError('Warehouse stock limit exceeded', 409)
        _capacity_check(session, bid, location, difference)
    # Claim exactly one open count, preventing concurrent/double posting.
    changed = session.execute(update(BinCycleCount).where(
        BinCycleCount.id == count_id, BinCycleCount.business_id == bid,
        BinCycleCount.status == 'open').values(
            status='posted', counted_on_hand=counted_on_hand,
            posted_by=actor_id, posted_at=utcnow()))
    if changed.rowcount != 1:
        raise DomainError('Bin cycle count is already closed', 409)
    # The protected-units expression includes the OLD bin quantity. The same
    # delta is applied to aggregate and bin stock, so compare the two deltas
    # together; outstanding putaway remains protected.
    changed = session.execute(update(StockLevel).where(
        StockLevel.id == stock.id, StockLevel.business_id == bid,
        StockLevel.on_hand == count.expected_warehouse_on_hand,
        StockLevel.on_hand + difference >= StockLevel.reserved,
        StockLevel.on_hand + difference >= 0,
        StockLevel.on_hand >= protected_units_expr()).values(
            on_hand=StockLevel.on_hand + difference))
    if changed.rowcount != 1:
        raise DomainError('Reserved, placed or pending inventory prevents reconciliation', 409)
    if current is not None:
        changed = session.execute(update(BinStock).where(
            BinStock.id == current.id, BinStock.business_id == bid,
            BinStock.on_hand == count.expected_on_hand,
            BinStock.allocated == count.expected_allocated).values(
                on_hand=counted_on_hand))
        if changed.rowcount != 1:
            raise DomainError('Physical bin stock changed; recount required', 409)
    elif counted_on_hand:
        session.add(BinStock(business_id=bid, warehouse_id=count.warehouse_id,
            bin_id=count.bin_id, product_id=count.product_id, on_hand=counted_on_hand,
            allocated=0))
    session.add(StockMovement(business_id=bid, warehouse_id=count.warehouse_id,
        product_id=count.product_id, user_id=actor_id, kind='bin_cycle_count',
        on_hand_delta=difference, reserved_delta=0,
        note=f'Bin {location.code} count #{count.id}: {count.note}'[:250]))
    session.flush()
    session.refresh(count)
    return count


def cancel_bin_count(session: Session, bid: int, count_id: int) -> BinCycleCount:
    count = _record(session, bid, count_id)
    changed = session.execute(update(BinCycleCount).where(
        BinCycleCount.id == count_id, BinCycleCount.business_id == bid,
        BinCycleCount.status == 'open').values(status='canceled'))
    if changed.rowcount != 1:
        raise DomainError('Only open bin counts can be canceled', 409)
    session.refresh(count)
    return count


def list_bin_counts(session: Session, bid: int) -> list[dict]:
    rows = session.execute(select(BinCycleCount, Product.sku, Warehouse.name,
                                  WarehouseBin.code).join(
        Product, Product.id == BinCycleCount.product_id).join(
        Warehouse, Warehouse.id == BinCycleCount.warehouse_id).join(
        WarehouseBin, WarehouseBin.id == BinCycleCount.bin_id).where(
        BinCycleCount.business_id == bid, Product.business_id == bid,
        Warehouse.business_id == bid, WarehouseBin.business_id == bid).order_by(
        BinCycleCount.id.desc()).limit(200))
    return [{"id": c.id, "warehouse_id": c.warehouse_id, "warehouse": warehouse,
             "bin_id": c.bin_id, "bin_code": bin_code, "sku": sku,
             "expected_on_hand": c.expected_on_hand,
             "counted_on_hand": c.counted_on_hand,
             "variance": None if c.counted_on_hand is None else c.counted_on_hand - c.expected_on_hand,
             "status": c.status, "note": c.note, "created_at": c.created_at.isoformat()}
            for c, sku, warehouse, bin_code in rows]
