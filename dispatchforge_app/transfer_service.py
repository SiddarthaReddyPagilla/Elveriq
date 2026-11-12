"""Tenant-scoped, retry-safe stock transfers.

The caller owns a SQL transaction and must commit on success / roll back on error.
PostgreSQL is the authoritative engine for concurrent transfers; SQLite is for
single-user demos and sequential unit tests only.
"""
import hashlib
import json
import re

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .errors import DomainError
from .models import InventoryTransfer, Product, StockLevel, StockMovement, User, Warehouse


KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}\Z")


def _fingerprint(source_id: int, destination_id: int, sku: str,
                 quantity: int, note: str) -> str:
    """Hash the normalized operation; exclude the requesting user on purpose."""
    payload = {"source_warehouse_id": source_id, "destination_warehouse_id": destination_id,
               "sku": sku, "quantity": quantity, "note": note}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def transfer_stock(session: Session, business_id: int, source_id: int,
                   destination_id: int, sku: str, quantity: int,
                   note: str = "", user_id: int | None = None,
                   idempotency_key: str | None = None) -> tuple[InventoryTransfer, bool]:
    """Transfer available stock once, returning (transfer, replayed).

    DB guarantees:
    - unique (business_id, idempotency_key) serializes same-key requests;
    - locks both stock rows by increasing primary key (PostgreSQL FOR UPDATE);
    - conditional debit, destination credit, transfer and two audit rows are in
      the caller's *single* transaction.
    """
    if not isinstance(source_id, int) or not isinstance(destination_id, int):
        raise DomainError("Warehouse IDs must be integers")
    if source_id == destination_id:
        raise DomainError("Source and destination must differ")
    if type(quantity) is not int or not 1 <= quantity <= 1_000_000:
        raise DomainError("Transfer quantity must be between 1 and 1,000,000")
    note = (note or "").strip()
    if len(note) > 250:
        raise DomainError("Transfer note is too long")
    sku = (sku or "").strip().upper()
    if not sku or len(sku) > 80:
        raise DomainError("SKU must contain 1–80 characters")
    if not isinstance(idempotency_key, str) or not KEY_PATTERN.fullmatch(idempotency_key):
        raise DomainError("Idempotency-Key must be 8–128 letters, digits, dots, colons, dashes or underscores")

    # The existing authorization model gives active owners/managers/staff access
    # to ALL warehouses within their business; no per-location grants exist yet.
    actor = session.scalar(select(User).where(
        User.id == user_id, User.business_id == business_id,
        User.role.in_(("owner", "manager", "staff"))))
    if actor is None:
        raise DomainError("Not permitted to transfer warehouse stock", 403)

    fingerprint = _fingerprint(source_id, destination_id, sku, quantity, note)
    previous = session.scalar(select(InventoryTransfer).where(
        InventoryTransfer.business_id == business_id,
        InventoryTransfer.idempotency_key == idempotency_key))
    if previous is not None:
        if previous.request_fingerprint != fingerprint:
            raise DomainError("Idempotency key already used for a different transfer", 409)
        return previous, True

    warehouse_ids = set(session.scalars(select(Warehouse.id).where(
        Warehouse.business_id == business_id,
        Warehouse.id.in_((source_id, destination_id)))).all())
    if warehouse_ids != {source_id, destination_id}:
        raise DomainError("Warehouse not found", 404)
    product_id = session.scalar(select(Product.id).where(
        Product.business_id == business_id, Product.sku == sku))
    if product_id is None:
        raise DomainError("Product not found", 404)

    # Insert BEFORE taking stock locks. PostgreSQL's unique index blocks another
    # transaction using the same key until this one commits or rolls back.
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        insert = postgres_insert(InventoryTransfer)
    elif dialect == "sqlite":
        insert = sqlite_insert(InventoryTransfer)
    else:
        raise RuntimeError("Stock transfer requires PostgreSQL or local SQLite")
    inserted = session.scalar(insert.values(
        business_id=business_id, source_warehouse_id=source_id,
        destination_warehouse_id=destination_id, product_id=product_id,
        quantity=quantity, note=note, user_id=user_id,
        idempotency_key=idempotency_key, request_fingerprint=fingerprint,
    ).on_conflict_do_nothing(
        index_elements=["business_id", "idempotency_key"]
    ).returning(InventoryTransfer.id))

    if inserted is None:
        # With PostgreSQL READ COMMITTED, the competing transaction is resolved
        # before this SELECT, so we can safely return its committed result.
        previous = session.scalar(select(InventoryTransfer).where(
            InventoryTransfer.business_id == business_id,
            InventoryTransfer.idempotency_key == idempotency_key))
        if previous is None:
            raise RuntimeError("Conflicting idempotency request was not committed")
        if previous.request_fingerprint != fingerprint:
            raise DomainError("Idempotency key already used for a different transfer", 409)
        return previous, True

    stock_pairs = dict(session.execute(select(StockLevel.warehouse_id, StockLevel.id).where(
        StockLevel.business_id == business_id,
        StockLevel.product_id == product_id,
        StockLevel.warehouse_id.in_((source_id, destination_id)))).all())
    if set(stock_pairs) != {source_id, destination_id}:
        raise DomainError("Warehouse inventory record not found", 404)

    # Every transfer locks the SAME two rows in ascending StockLevel.id order,
    # regardless of the source/destination direction. Other inventory writers
    # using UPDATE must wait on these locks as well.
    for stock_id in sorted(stock_pairs.values()):
        session.scalar(select(StockLevel).where(StockLevel.id == stock_id)
                       .with_for_update().execution_options(populate_existing=True))

    source_update = session.execute(update(StockLevel).where(
        StockLevel.id == stock_pairs[source_id],
        StockLevel.business_id == business_id,
        StockLevel.on_hand - StockLevel.reserved >= quantity,
    ).values(on_hand=StockLevel.on_hand - quantity))
    if source_update.rowcount != 1:
        raise DomainError("Not enough unreserved stock to transfer", 409)

    destination_update = session.execute(update(StockLevel).where(
        StockLevel.id == stock_pairs[destination_id],
        StockLevel.business_id == business_id,
    ).values(on_hand=StockLevel.on_hand + quantity))
    if destination_update.rowcount != 1:
        raise DomainError("Destination stock record unavailable", 409)

    transfer = session.get(InventoryTransfer, inserted)
    for warehouse_id, delta, kind in (
        (source_id, -quantity, "transfer_out"),
        (destination_id, quantity, "transfer_in"),
    ):
        session.add(StockMovement(
            business_id=business_id, warehouse_id=warehouse_id,
            product_id=product_id, user_id=user_id, kind=kind,
            on_hand_delta=delta, reserved_delta=0, transfer_id=inserted,
            note=f"Transfer #{inserted}: {note}"[:250],
        ))
    session.flush()
    return transfer, False


def list_transfers(session: Session, business_id: int, limit: int = 100) -> list[dict]:
    transfers = session.scalars(select(InventoryTransfer).where(
        InventoryTransfer.business_id == business_id)
        .order_by(InventoryTransfer.id.desc()).limit(min(max(limit, 1), 200))).all()
    if not transfers:
        return []
    names = dict(session.execute(select(Warehouse.id, Warehouse.name).where(
        Warehouse.business_id == business_id)).all())
    products = dict(session.execute(select(Product.id, Product.sku).where(
        Product.business_id == business_id)).all())
    return [{"id": t.id, "sku": products[t.product_id], "quantity": t.quantity,
             "source": names[t.source_warehouse_id],
             "destination": names[t.destination_warehouse_id],
             "source_warehouse_id": t.source_warehouse_id,
             "destination_warehouse_id": t.destination_warehouse_id,
             "note": t.note, "created_at": t.created_at.isoformat()} for t in transfers]
