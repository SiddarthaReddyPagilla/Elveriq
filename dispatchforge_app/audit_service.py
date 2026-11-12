"""Cursor-paginated, tenant-safe stock history for operational investigation."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from .errors import DomainError
from .models import StockMovement, Product, Warehouse


def audit_stock(session: Session, business_id: int, *, kind: str | None = None,
                sku: str | None = None, warehouse_id: int | None = None,
                before_id: int | None = None, limit: int = 50) -> dict:
    if not 1 <= limit <= 200:
        raise DomainError("Limit must be between 1 and 200")
    query = (select(StockMovement, Product.sku, Warehouse.name)
        .join(Product, Product.id == StockMovement.product_id)
        .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
        .where(StockMovement.business_id == business_id,
               Product.business_id == business_id, Warehouse.business_id == business_id))
    if kind:
        query = query.where(StockMovement.kind == kind)
    if sku:
        query = query.where(Product.sku == sku.strip().upper())
    if warehouse_id is not None:
        query = query.where(StockMovement.warehouse_id == warehouse_id)
    if before_id is not None:
        query = query.where(StockMovement.id < before_id)
    records = session.execute(query.order_by(StockMovement.id.desc()).limit(limit+1)).all()
    has_more = len(records) > limit
    records = records[:limit]
    return {"items": [{"id": movement.id, "sku": sku_name, "warehouse": warehouse,
              "kind": movement.kind, "on_hand_delta": movement.on_hand_delta,
              "reserved_delta": movement.reserved_delta, "note": movement.note,
              "user_id": movement.user_id, "transfer_id": movement.transfer_id,
              "created_at": movement.created_at.isoformat()}
            for movement, sku_name, warehouse in records],
            "next_cursor": records[-1][0].id if has_more and records else None}
