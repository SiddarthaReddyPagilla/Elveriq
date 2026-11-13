"""Tenant-scoped inventory commands and queries with an append-only movement trail."""
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .errors import DomainError
from .models import Product, Warehouse, StockLevel, StockMovement, Supplier


def clean_text(value: str, label: str, max_length: int = 150) -> str:
    value = (value or "").strip()
    if not value or len(value) > max_length:
        raise DomainError(f"{label} must contain 1–{max_length} characters")
    return value


def create_warehouse(session: Session, business_id: int, name: str, city: str = "") -> Warehouse:
    name = clean_text(name, "Warehouse name", 120)
    if session.scalar(select(Warehouse.id).where(Warehouse.business_id == business_id, Warehouse.name == name)):
        raise DomainError("A warehouse with that name already exists", 409)
    warehouse = Warehouse(business_id=business_id, name=name, city=(city or "").strip()[:120])
    session.add(warehouse)
    session.flush()
    for product_id in session.scalars(select(Product.id).where(Product.business_id == business_id)):
        session.add(StockLevel(business_id=business_id, warehouse_id=warehouse.id, product_id=product_id))
    session.flush()
    return warehouse


def create_product(session: Session, business_id: int, sku: str, name: str,
                   price_cents: int = 0, reorder_point: int = 5, unit: str = "each") -> Product:
    sku = clean_text(sku, "SKU", 80).upper()
    name = clean_text(name, "Product name", 180)
    unit = clean_text(unit, "Unit", 24)
    if not 0 <= price_cents <= 100_000_000 or not 0 <= reorder_point <= 1_000_000:
        raise DomainError("Price or reorder point is outside allowed range")
    if session.scalar(select(Product.id).where(Product.business_id == business_id, Product.sku == sku)):
        raise DomainError(f"SKU {sku} already exists", 409)
    product = Product(business_id=business_id, sku=sku, name=name, price_cents=price_cents,
                      reorder_point=reorder_point, unit=unit)
    session.add(product)
    session.flush()
    for warehouse_id in session.scalars(select(Warehouse.id).where(Warehouse.business_id == business_id)):
        session.add(StockLevel(business_id=business_id, warehouse_id=warehouse_id, product_id=product.id))
    session.flush()
    return product


def create_supplier(session: Session, business_id: int, name: str, email: str = "") -> Supplier:
    name = clean_text(name, "Supplier name", 150)
    if session.scalar(select(Supplier.id).where(Supplier.business_id == business_id, Supplier.name == name)):
        raise DomainError("Supplier already exists", 409)
    supplier = Supplier(business_id=business_id, name=name, email=(email or "").strip()[:254])
    session.add(supplier)
    session.flush()
    return supplier


def get_stock(session: Session, business_id: int, warehouse_id: int, sku: str):
    warehouse = session.scalar(select(Warehouse).where(Warehouse.id == warehouse_id,
                                                      Warehouse.business_id == business_id))
    if warehouse is None:
        raise DomainError("Warehouse not found", 404)
    product = session.scalar(select(Product).where(Product.business_id == business_id,
                                                  Product.sku == sku.strip().upper()))
    if product is None:
        raise DomainError("Product not found", 404)
    stock = session.scalar(select(StockLevel).where(StockLevel.business_id == business_id,
                                                   StockLevel.warehouse_id == warehouse_id,
                                                   StockLevel.product_id == product.id))
    if stock is None:
        raise DomainError("Stock record not found", 404)
    return product, stock


def apply_stock_delta(session: Session, business_id: int, warehouse_id: int, sku: str,
                      change: int, kind: str, note: str = "", user_id: int | None = None):
    if change == 0 or abs(change) > 1_000_000:
        raise DomainError("Quantity change must be nonzero and within 1,000,000 units")
    product, stock = get_stock(session, business_id, warehouse_id, sku)
    from .warehouse_execution import protected_units_expr
    # Conditional update stops reductions from using already-reserved inventory.
    result = session.execute(
        update(StockLevel).where(
            StockLevel.id == stock.id,
            StockLevel.business_id == business_id,
            StockLevel.on_hand + change >= StockLevel.reserved,
            StockLevel.on_hand + change >= 0,
            StockLevel.on_hand + change >= protected_units_expr(),
        ).values(on_hand=StockLevel.on_hand + change)
    )
    if result.rowcount != 1:
        raise DomainError("Insufficient unreserved inventory for this adjustment", 409)
    session.add(StockMovement(business_id=business_id, warehouse_id=warehouse_id,
                              product_id=product.id, user_id=user_id, kind=kind,
                              on_hand_delta=change, reserved_delta=0,
                              note=(note or "").strip()[:250]))
    session.flush()
    session.refresh(stock)
    return stock


def list_inventory(session: Session, business_id: int) -> list[dict]:
    statement = (
        select(Product, Warehouse, StockLevel)
        .join(StockLevel, StockLevel.product_id == Product.id)
        .join(Warehouse, Warehouse.id == StockLevel.warehouse_id)
        .where(Product.business_id == business_id, Warehouse.business_id == business_id,
               StockLevel.business_id == business_id)
        .order_by(Product.name, Warehouse.name)
    )
    return [
        {"sku": p.sku, "name": p.name, "unit": p.unit, "price_cents": p.price_cents,
         "reorder_point": p.reorder_point, "warehouse_id": w.id, "warehouse": w.name,
         "on_hand": s.on_hand, "reserved": s.reserved, "available": s.on_hand - s.reserved,
         "low_stock": s.on_hand - s.reserved <= p.reorder_point}
        for p, w, s in session.execute(statement)
    ]


def list_movements(session: Session, business_id: int, limit: int = 40) -> list[dict]:
    q = (select(StockMovement, Product.sku, Warehouse.name)
         .join(Product, Product.id == StockMovement.product_id)
         .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
         .where(StockMovement.business_id == business_id)
         .order_by(StockMovement.id.desc()).limit(min(limit, 200)))
    return [
        {"id": m.id, "sku": sku, "warehouse": warehouse, "kind": m.kind,
         "on_hand_delta": m.on_hand_delta, "reserved_delta": m.reserved_delta,
         "note": m.note, "transfer_id": m.transfer_id,
         "created_at": m.created_at.isoformat()}
        for m, sku, warehouse in session.execute(q)
    ]
