"""Atomic cross-warehouse transfers with two-sided stock audit entries."""
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .errors import DomainError
from .inventory_service import get_stock
from .models import InventoryTransfer, Product, StockLevel, StockMovement, Warehouse


def transfer_stock(session: Session, business_id: int, source_id: int,
                   destination_id: int, sku: str, quantity: int,
                   note: str = "", user_id: int | None = None) -> InventoryTransfer:
    if source_id == destination_id:
        raise DomainError("Source and destination must differ")
    if type(quantity) is not int or not 1 <= quantity <= 1_000_000:
        raise DomainError("Transfer quantity must be between 1 and 1,000,000")
    if len(note or "") > 250:
        raise DomainError("Transfer note is too long")
    product, source = get_stock(session, business_id, source_id, sku)
    _, destination = get_stock(session, business_id, destination_id, sku)
    result = session.execute(update(StockLevel).where(
        StockLevel.id == source.id,
        StockLevel.business_id == business_id,
        StockLevel.on_hand - StockLevel.reserved >= quantity,
    ).values(on_hand=StockLevel.on_hand - quantity))
    if result.rowcount != 1:
        raise DomainError("Not enough unreserved stock to transfer", 409)
    result = session.execute(update(StockLevel).where(
        StockLevel.id == destination.id, StockLevel.business_id == business_id,
    ).values(on_hand=StockLevel.on_hand + quantity))
    if result.rowcount != 1:
        raise DomainError("Destination stock record unavailable", 409)
    transfer = InventoryTransfer(business_id=business_id,
        source_warehouse_id=source_id, destination_warehouse_id=destination_id,
        product_id=product.id, quantity=quantity, note=(note or "").strip(),
        user_id=user_id)
    session.add(transfer)
    session.flush()
    for warehouse_id, delta, kind in ((source_id, -quantity, "transfer_out"),
                                      (destination_id, quantity, "transfer_in")):
        session.add(StockMovement(business_id=business_id, warehouse_id=warehouse_id,
            product_id=product.id, user_id=user_id, kind=kind,
            on_hand_delta=delta, reserved_delta=0,
            note=f"Transfer #{transfer.id}: {transfer.note}"[:250]))
    session.flush()
    return transfer


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
