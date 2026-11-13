"""Tenant-safe warehouse location and work orchestration.

This increment deliberately keeps StockLevel as the accounting authority. BinStock
tracks a subset of physically placed inventory; the remainder is unlocated.
Putaway and relocation tasks do NOT debit the warehouse accounting balance.
See docs/WAREHOUSE_EXECUTION.md for boundaries before enabling picking.
"""
import hashlib
import json
import re
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from .errors import DomainError
from .inventory_service import clean_text, get_stock
from .models import (BinStock, Product, StockLevel, User, Warehouse, WarehouseBin,
                     WarehouseTask, WarehouseTaskEvent, utcnow)

CODE = re.compile(r"[A-Z0-9][A-Z0-9_.:/-]{0,63}\Z")
ACTIVE = ("queued", "assigned", "in_progress")
KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}\Z")


def protected_units_expr():
    """SQL-correlated committed placements and pending unlocated -> bin work.

    Use inside the same atomic conditional stock UPDATE that reduces on_hand;
    a separate Python check could race another transaction.
    """
    placed = (select(func.coalesce(func.sum(BinStock.on_hand), 0))
              .where(BinStock.business_id == StockLevel.business_id,
                     BinStock.warehouse_id == StockLevel.warehouse_id,
                     BinStock.product_id == StockLevel.product_id)
              .correlate(StockLevel).scalar_subquery())
    pending = (select(func.coalesce(func.sum(WarehouseTask.quantity), 0))
               .where(WarehouseTask.business_id == StockLevel.business_id,
                      WarehouseTask.warehouse_id == StockLevel.warehouse_id,
                      WarehouseTask.product_id == StockLevel.product_id,
                      WarehouseTask.kind == "putaway", WarehouseTask.status.in_(ACTIVE))
               .correlate(StockLevel).scalar_subquery())
    return placed + pending


def code(value: str) -> str:
    result = (value or "").strip().upper()
    if not CODE.fullmatch(result):
        raise DomainError("Bin code must be 1–64 letters, digits, dashes, dots, colons, slashes or underscores")
    return result


def create_bin(session: Session, bid: int, wid: int, bin_code: str,
               zone: str = "", aisle: str = "", rack: str = "", shelf: str = "",
               capacity_units: int | None = None) -> WarehouseBin:
    if not session.scalar(select(Warehouse.id).where(Warehouse.id == wid, Warehouse.business_id == bid)):
        raise DomainError("Warehouse not found", 404)
    bin_code = code(bin_code)
    if capacity_units is not None and (type(capacity_units) is not int or not 1 <= capacity_units <= 10_000_000):
        raise DomainError("Bin capacity must be between 1 and 10,000,000 units")
    if session.scalar(select(WarehouseBin.id).where(WarehouseBin.business_id == bid,
            WarehouseBin.warehouse_id == wid, WarehouseBin.code == bin_code)):
        raise DomainError("Bin code already exists in this warehouse", 409)
    row = WarehouseBin(business_id=bid, warehouse_id=wid, code=bin_code,
                       zone=(zone or "").strip()[:60], aisle=(aisle or "").strip()[:40],
                       rack=(rack or "").strip()[:40], shelf=(shelf or "").strip()[:40],
                       capacity_units=capacity_units)
    session.add(row)
    session.flush()
    return row


def list_bins(session: Session, bid: int, wid: int | None = None) -> list[dict]:
    q = select(WarehouseBin, Warehouse.name).join(Warehouse, Warehouse.id == WarehouseBin.warehouse_id).where(
        WarehouseBin.business_id == bid, Warehouse.business_id == bid)
    if wid is not None:
        q = q.where(WarehouseBin.warehouse_id == wid)
    rows = session.execute(q.order_by(Warehouse.name, WarehouseBin.code)).all()
    used = dict(session.execute(select(BinStock.bin_id, func.sum(BinStock.on_hand)).where(
        BinStock.business_id == bid).group_by(BinStock.bin_id)).all())
    return [{"id": b.id, "warehouse_id": b.warehouse_id, "warehouse": name, "code": b.code,
             "zone": b.zone, "aisle": b.aisle, "rack": b.rack, "shelf": b.shelf,
             "capacity_units": b.capacity_units, "placed_units": used.get(b.id, 0),
             "active": b.active} for b, name in rows]


def list_bin_stock(session: Session, bid: int, wid: int | None = None) -> list[dict]:
    q = (select(BinStock, WarehouseBin.code, Product.sku)
         .join(WarehouseBin, WarehouseBin.id == BinStock.bin_id)
         .join(Product, Product.id == BinStock.product_id)
         .where(BinStock.business_id == bid, WarehouseBin.business_id == bid, Product.business_id == bid))
    if wid is not None:
        q = q.where(BinStock.warehouse_id == wid)
    return [{"bin_id": b.bin_id, "warehouse_id": b.warehouse_id, "bin_code": bin_code,
             "sku": sku, "on_hand": b.on_hand, "committed_to_moves": b.allocated,
             "available": b.on_hand - b.allocated} for b, bin_code, sku in session.execute(
                 q.order_by(WarehouseBin.code, Product.sku))]


def location_summary(session: Session, bid: int, wid: int | None = None) -> list[dict]:
    q = (select(StockLevel, Product.sku, Warehouse.name).join(Product, StockLevel.product_id == Product.id)
         .join(Warehouse, StockLevel.warehouse_id == Warehouse.id).where(
             StockLevel.business_id == bid, Product.business_id == bid, Warehouse.business_id == bid))
    if wid is not None:
        q = q.where(StockLevel.warehouse_id == wid)
    placed = {}
    # Composite-key dictionary is built explicitly to avoid casting dialect Row objects.
    for warehouse_id, product_id, qty in session.execute(select(BinStock.warehouse_id,
            BinStock.product_id, func.sum(BinStock.on_hand)).where(BinStock.business_id == bid)
            .group_by(BinStock.warehouse_id, BinStock.product_id)):
        placed[(warehouse_id, product_id)] = qty
    pending = {}
    for warehouse_id, product_id, qty in session.execute(select(WarehouseTask.warehouse_id,
            WarehouseTask.product_id, func.sum(WarehouseTask.quantity)).where(
            WarehouseTask.business_id == bid, WarehouseTask.kind == "putaway",
            WarehouseTask.status.in_(ACTIVE)).group_by(WarehouseTask.warehouse_id, WarehouseTask.product_id)):
        pending[(warehouse_id, product_id)] = qty
    return [{"warehouse_id": s.warehouse_id, "warehouse": name, "sku": sku,
             "on_hand": s.on_hand, "placed": placed.get((s.warehouse_id, s.product_id), 0),
             "unlocated": s.on_hand - placed.get((s.warehouse_id, s.product_id), 0),
             "pending_putaway": pending.get((s.warehouse_id, s.product_id), 0)}
            for s, sku, name in session.execute(q.order_by(Warehouse.name, Product.sku))]


def _bin(session: Session, bid: int, wid: int, bin_id: int) -> WarehouseBin:
    result = session.scalar(select(WarehouseBin).where(WarehouseBin.id == bin_id,
        WarehouseBin.business_id == bid, WarehouseBin.warehouse_id == wid))
    if result is None:
        raise DomainError("Bin not found in this warehouse", 404)
    if not result.active:
        raise DomainError("Bin is blocked for new work", 409)
    return result


def _stock_guard(session: Session, bid: int, wid: int, pid: int) -> StockLevel:
    """Warehouse SKU row acts as the shared transaction serialization lock."""
    stock = session.scalar(select(StockLevel).where(
        StockLevel.business_id == bid, StockLevel.warehouse_id == wid,
        StockLevel.product_id == pid).with_for_update().execution_options(populate_existing=True))
    if stock is None:
        raise DomainError("Warehouse stock record not found", 404)
    return stock


def _total_placed(session: Session, bid: int, wid: int, pid: int) -> int:
    return session.scalar(select(func.coalesce(func.sum(BinStock.on_hand), 0)).where(
        BinStock.business_id == bid, BinStock.warehouse_id == wid, BinStock.product_id == pid))


def _pending_putaway(session: Session, bid: int, wid: int, pid: int) -> int:
    return session.scalar(select(func.coalesce(func.sum(WarehouseTask.quantity), 0)).where(
        WarehouseTask.business_id == bid, WarehouseTask.warehouse_id == wid,
        WarehouseTask.product_id == pid, WarehouseTask.kind == "putaway",
        WarehouseTask.status.in_(ACTIVE)))


def _inbound_to_bin(session: Session, bid: int, bin_id: int) -> int:
    return session.scalar(select(func.coalesce(func.sum(WarehouseTask.quantity), 0)).where(
        WarehouseTask.business_id == bid, WarehouseTask.to_bin_id == bin_id,
        WarehouseTask.status.in_(ACTIVE)))


def _capacity_check(session: Session, bid: int, destination: WarehouseBin, qty: int):
    if destination.capacity_units is None:
        return
    placed = session.scalar(select(func.coalesce(func.sum(BinStock.on_hand), 0)).where(
        BinStock.business_id == bid, BinStock.bin_id == destination.id))
    inbound = _inbound_to_bin(session, bid, destination.id)
    if placed + inbound + qty > destination.capacity_units:
        raise DomainError("Bin capacity exceeded including queued work", 409)


def _event(session: Session, task: WarehouseTask, actor_id: int, action: str, note: str = ""):
    session.add(WarehouseTaskEvent(business_id=task.business_id, task_id=task.id,
                 actor_id=actor_id, action=action, detail=note[:250]))


def _fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def create_task(session: Session, bid: int, wid: int, sku: str, kind: str,
                to_bin_id: int, qty: int, actor_id: int,
                from_bin_id: int | None = None, assignee_id: int | None = None,
                priority: int = 3, note: str = "", idempotency_key: str | None = None):
    if kind not in ("putaway", "move", "unlocate"):
        raise DomainError("Task type must be putaway, move, or unlocate")
    if type(qty) is not int or not 1 <= qty <= 1_000_000:
        raise DomainError("Quantity must be between 1 and 1,000,000")
    if type(priority) is not int or not 1 <= priority <= 5:
        raise DomainError("Priority must be between 1 and 5")
    if len(note or "") > 250:
        raise DomainError("Task note is too long")
    if not isinstance(idempotency_key, str) or not KEY.fullmatch(idempotency_key):
        raise DomainError("Idempotency-Key required (8–128 safe characters)")
    if kind == "putaway" and (from_bin_id is not None or to_bin_id is None):
        raise DomainError("Putaway requires a destination bin and starts from unlocated stock")
    if kind == "move" and (from_bin_id is None or to_bin_id is None or from_bin_id == to_bin_id):
        raise DomainError("Move requires two different bins")
    if kind == "unlocate" and (from_bin_id is None or to_bin_id is not None):
        raise DomainError("Unlocate requires only a source bin; destination is the unlocated staging pool")
    sku = clean_text(sku, "SKU", 80).upper()
    norm = {"warehouse_id": wid, "sku": sku, "kind": kind, "to_bin_id": to_bin_id,
            "from_bin_id": from_bin_id, "quantity": qty, "assignee_id": assignee_id,
            "priority": priority, "note": (note or "").strip()}
    fingerprint = _fingerprint(norm)
    previous = session.scalar(select(WarehouseTask).where(
        WarehouseTask.business_id == bid, WarehouseTask.idempotency_key == idempotency_key))
    if previous:
        if previous.request_fingerprint != fingerprint:
            raise DomainError("Idempotency key reused with different task details", 409)
        return previous, True
    product, _ = get_stock(session, bid, wid, sku)
    stock = _stock_guard(session, bid, wid, product.id)
    # A second check after locking serializes same-key retries against task creation.
    previous = session.scalar(select(WarehouseTask).where(
        WarehouseTask.business_id == bid, WarehouseTask.idempotency_key == idempotency_key))
    if previous:
        if previous.request_fingerprint != fingerprint:
            raise DomainError("Idempotency key reused with different task details", 409)
        return previous, True
    if assignee_id is not None and not session.scalar(select(User.id).where(
        User.id == assignee_id, User.business_id == bid, User.role.in_(("owner", "manager", "staff")))):
        raise DomainError("Assignee not found in workspace", 404)
    destination = _bin(session, bid, wid, to_bin_id) if to_bin_id is not None else None
    if kind in ("move", "unlocate"):
        _bin(session, bid, wid, from_bin_id)
    if destination:
        # Serialize capacity across SKU rows using the destination bin lock.
        session.scalar(select(WarehouseBin).where(WarehouseBin.id == destination.id).with_for_update())
        _capacity_check(session, bid, destination, qty)
    if kind == "putaway":
        if stock.on_hand - _total_placed(session, bid, wid, product.id) - _pending_putaway(session, bid, wid, product.id) < qty:
            raise DomainError("Insufficient unlocated stock not already queued for putaway", 409)
    elif not session.scalar(select(BinStock.id).where(BinStock.business_id == bid,
            BinStock.bin_id == from_bin_id, BinStock.product_id == product.id,
            BinStock.on_hand - BinStock.allocated >= qty)):
        raise DomainError("Not enough unallocated stock in source bin", 409)

    # Unique-key upsert is authoritative across concurrent requests, including
    # requests using the same key for two DIFFERENT product rows.
    values = dict(business_id=bid, warehouse_id=wid, product_id=product.id,
        kind=kind, from_bin_id=from_bin_id, to_bin_id=to_bin_id,
        quantity=qty, priority=priority, note=norm["note"], created_by=actor_id,
        assigned_user_id=assignee_id, status="assigned" if assignee_id else "queued",
        idempotency_key=idempotency_key, request_fingerprint=fingerprint)
    dialect = session.get_bind().dialect.name
    statement = postgres_insert(WarehouseTask) if dialect == "postgresql" else sqlite_insert(WarehouseTask)
    inserted = session.scalar(statement.values(**values).on_conflict_do_nothing(
        index_elements=["business_id", "idempotency_key"]).returning(WarehouseTask.id))
    if inserted is None:
        existing = session.scalar(select(WarehouseTask).where(
            WarehouseTask.business_id == bid, WarehouseTask.idempotency_key == idempotency_key))
        if existing is None:
            raise RuntimeError("Idempotency result not visible after concurrent write")
        if existing.request_fingerprint != fingerprint:
            raise DomainError("Idempotency key reused with different task details", 409)
        return existing, True
    task = session.get(WarehouseTask, inserted)
    if kind in ("move", "unlocate"):
        result = session.execute(update(BinStock).where(BinStock.business_id == bid,
            BinStock.warehouse_id == wid, BinStock.bin_id == from_bin_id,
            BinStock.product_id == product.id, BinStock.on_hand - BinStock.allocated >= qty
            ).values(allocated=BinStock.allocated + qty))
        if result.rowcount != 1:
            raise DomainError("Not enough unallocated stock in source bin", 409)
    _event(session, task, actor_id, "created")
    return task, False


def _task(session: Session, bid: int, task_id: int) -> WarehouseTask:
    result = session.scalar(select(WarehouseTask).where(
        WarehouseTask.id == task_id, WarehouseTask.business_id == bid))
    if not result:
        raise DomainError("Warehouse task not found", 404)
    return result


def assign_task(session: Session, bid: int, task_id: int, actor_id: int,
                assignee_id: int | None):
    task = _task(session, bid, task_id)
    _stock_guard(session, bid, task.warehouse_id, task.product_id)
    session.refresh(task)
    if task.status not in ("queued", "assigned"):
        raise DomainError("Only queued or assigned work can be reassigned", 409)
    if assignee_id is not None and not session.scalar(select(User.id).where(
        User.id == assignee_id, User.business_id == bid,
        User.role.in_(("owner", "manager", "staff")))):
        raise DomainError("Assignee not found in workspace", 404)
    task.assigned_user_id = assignee_id
    task.status = "assigned" if assignee_id else "queued"
    _event(session, task, actor_id, "assigned" if assignee_id else "unassigned", str(assignee_id or ""))
    session.flush()
    return task


def claim_task(session: Session, bid: int, task_id: int, actor_id: int):
    task = _task(session, bid, task_id)
    _stock_guard(session, bid, task.warehouse_id, task.product_id)
    session.refresh(task)
    result = session.execute(update(WarehouseTask).where(WarehouseTask.id == task_id,
        WarehouseTask.business_id == bid, WarehouseTask.status == "queued",
        WarehouseTask.assigned_user_id.is_(None)).values(
        assigned_user_id=actor_id, status="assigned"))
    if result.rowcount != 1:
        raise DomainError("Task is already assigned or closed", 409)
    _event(session, task, actor_id, "claimed")
    session.refresh(task)
    return task


def start_task(session: Session, bid: int, task_id: int, actor_id: int):
    task = _task(session, bid, task_id)
    _stock_guard(session, bid, task.warehouse_id, task.product_id)
    session.refresh(task)
    result = session.execute(update(WarehouseTask).where(WarehouseTask.id == task_id,
        WarehouseTask.business_id == bid, WarehouseTask.status == "assigned",
        WarehouseTask.assigned_user_id == actor_id).values(status="in_progress"))
    if result.rowcount != 1:
        raise DomainError("Task must be assigned to you before starting", 409)
    _event(session, task, actor_id, "started")
    session.refresh(task)
    return task


def cancel_task(session: Session, bid: int, task_id: int, actor_id: int):
    task = _task(session, bid, task_id)
    _stock_guard(session, bid, task.warehouse_id, task.product_id)
    session.refresh(task)
    if task.status not in ACTIVE:
        raise DomainError("Task is already closed", 409)
    if task.kind in ("move", "unlocate"):
        result = session.execute(update(BinStock).where(BinStock.business_id == bid,
            BinStock.bin_id == task.from_bin_id, BinStock.product_id == task.product_id,
            BinStock.allocated >= task.quantity).values(allocated=BinStock.allocated - task.quantity))
        if result.rowcount != 1:
            raise DomainError("Source bin reservation could not be released", 409)
    task.status = "canceled"
    _event(session, task, actor_id, "canceled")
    session.flush()
    return task


def _credit_bin(session: Session, task: WarehouseTask):
    values = {"business_id": task.business_id, "warehouse_id": task.warehouse_id,
              "bin_id": task.to_bin_id, "product_id": task.product_id,
              "on_hand": task.quantity, "allocated": 0}
    dialect = session.get_bind().dialect.name
    statement = postgres_insert(BinStock) if dialect == "postgresql" else sqlite_insert(BinStock)
    # Only these two engines are supported by the application.
    stmt = statement.values(**values).on_conflict_do_update(
        index_elements=["bin_id", "product_id"],
        set_={"on_hand": BinStock.on_hand + task.quantity})
    session.execute(stmt)


def complete_task(session: Session, bid: int, task_id: int, actor_id: int,
                  scan_sku: str, scan_to_bin: str, scan_from_bin: str | None = None):
    task = _task(session, bid, task_id)
    _stock_guard(session, bid, task.warehouse_id, task.product_id)
    session.refresh(task)
    product = session.scalar(select(Product).where(Product.id == task.product_id,
                                                   Product.business_id == bid))
    dest = session.scalar(select(WarehouseBin).where(WarehouseBin.id == task.to_bin_id,
                                                    WarehouseBin.business_id == bid))
    source = None
    if task.from_bin_id:
        source = session.scalar(select(WarehouseBin).where(
            WarehouseBin.id == task.from_bin_id, WarehouseBin.business_id == bid))
    scans = {"sku": (scan_sku or "").strip().upper(),
             "to": (scan_to_bin or "").strip().upper(),
             "from": (scan_from_bin or "").strip().upper()}
    fingerprint = _fingerprint(scans)
    if task.status == "completed":
        if task.completed_by == actor_id and task.scan_fingerprint == fingerprint:
            return task, True
        raise DomainError("Task already completed with different verification", 409)
    if task.status != "in_progress" or task.assigned_user_id != actor_id:
        raise DomainError("Only the assigned worker can complete an in-progress task", 409)
    if (task.kind != "unlocate" and (not dest or not dest.active)) or (source and not source.active):
        raise DomainError("Location blocked or removed", 409)
    if scans["sku"] != product.sku or scans["to"] != (dest.code if dest else "UNLOCATED") or (
            source and scans["from"] != source.code):
        _event(session, task, actor_id, "scan_rejected", "Scanned product/location mismatch")
        # Route commits this event separately on validation failure; no stock changes.
        session.flush()
        raise DomainError("Scan verification failed: check SKU and source/destination bin codes", 409)
    if task.kind in ("move", "unlocate"):
        result = session.execute(update(BinStock).where(
            BinStock.business_id == bid, BinStock.bin_id == source.id,
            BinStock.product_id == product.id,
            BinStock.on_hand >= task.quantity,
            BinStock.allocated >= task.quantity).values(
                on_hand=BinStock.on_hand - task.quantity,
                allocated=BinStock.allocated - task.quantity))
        if result.rowcount != 1:
            raise DomainError("Source bin stock cannot be confirmed", 409)
    else:
        # Outstanding putaway was reserved at task creation by locking StockLevel.
        # This state transition substitutes quantity for pending work without
        # changing the accounting quantity on hand.
        protected = _total_placed(session, bid, task.warehouse_id, product.id)
        if _stock_guard(session, bid, task.warehouse_id, product.id).on_hand < protected + task.quantity:
            raise DomainError("Warehouse stock no longer supports this putaway", 409)
    if task.kind != "unlocate":
        _credit_bin(session, task)
    task.status = "completed"
    task.completed_by = actor_id
    task.scan_fingerprint = fingerprint
    task.completed_at = utcnow()
    _event(session, task, actor_id, "completed", f"SKU {product.sku}, destination {dest.code if dest else 'UNLOCATED'}")
    session.flush()
    return task, False


def task_detail(task: WarehouseTask, products: dict, bins: dict) -> dict:
    return {"id": task.id, "warehouse_id": task.warehouse_id,
            "sku": products[task.product_id], "kind": task.kind,
            "from_bin_id": task.from_bin_id,
            "from_bin": bins.get(task.from_bin_id),
            "to_bin_id": task.to_bin_id, "to_bin": bins.get(task.to_bin_id, "UNLOCATED"),
            "quantity": task.quantity, "priority": task.priority,
            "note": task.note, "status": task.status,
            "assigned_user_id": task.assigned_user_id,
            "created_at": task.created_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None}


def list_tasks(session: Session, bid: int, wid: int | None = None) -> list[dict]:
    q = select(WarehouseTask).where(WarehouseTask.business_id == bid)
    if wid is not None:
        q = q.where(WarehouseTask.warehouse_id == wid)
    tasks = session.scalars(q.order_by(WarehouseTask.id.desc()).limit(200)).all()
    if not tasks:
        return []
    products = dict(session.execute(select(Product.id, Product.sku).where(Product.business_id == bid)).all())
    bins = dict(session.execute(select(WarehouseBin.id, WarehouseBin.code).where(WarehouseBin.business_id == bid)).all())
    return [task_detail(t, products, bins) for t in tasks]


def task_events(session: Session, bid: int, task_id: int) -> list[dict]:
    _task(session, bid, task_id)
    return [{"id": x.id, "action": x.action, "actor_id": x.actor_id,
             "detail": x.detail, "created_at": x.created_at.isoformat()} for x in session.scalars(
                 select(WarehouseTaskEvent).where(WarehouseTaskEvent.business_id == bid,
                 WarehouseTaskEvent.task_id == task_id).order_by(WarehouseTaskEvent.id))]
