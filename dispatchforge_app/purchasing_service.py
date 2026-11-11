"""Purchase orders, supplier receiving and tenant-scoped inventory accounting.

This is a warehouse-software prototype: recording goods receipt requires staff
confirmation; no external supplier has actually shipped anything.
"""
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .errors import DomainError
from .models import PurchaseOrder, PurchaseOrderLine, Product, Supplier, Warehouse
from .inventory_service import apply_stock_delta, clean_text


def create_purchase_order(session: Session, business_id: int, supplier_id: int,
                          warehouse_id: int, expected_date: str | None,
                          reference: str, items: list[dict]) -> PurchaseOrder:
    supplier = session.scalar(select(Supplier).where(
        Supplier.id == supplier_id, Supplier.business_id == business_id))
    warehouse = session.scalar(select(Warehouse).where(
        Warehouse.id == warehouse_id, Warehouse.business_id == business_id))
    if supplier is None or warehouse is None:
        raise DomainError("Supplier or warehouse not found in this workspace", 404)
    reference = clean_text(reference, "Purchase reference", 100)
    if session.scalar(select(PurchaseOrder.id).where(
        PurchaseOrder.business_id == business_id, PurchaseOrder.reference == reference)):
        raise DomainError("Purchase reference already exists", 409)
    if not 1 <= len(items) <= 100:
        raise DomainError("Purchase order requires 1–100 items")
    order = PurchaseOrder(business_id=business_id, warehouse_id=warehouse_id,
                          supplier_id=supplier_id, expected_date=expected_date,
                          reference=reference, status="ordered")
    session.add(order)
    session.flush()
    seen = set()
    for item in items:
        sku = (item.get("sku") or "").strip().upper()
        quantity = item.get("quantity")
        if sku in seen:
            raise DomainError("Repeated SKU in a purchase order is not allowed")
        seen.add(sku)
        if not isinstance(quantity, int) or not 1 <= quantity <= 1_000_000:
            raise DomainError("Invalid purchase quantity")
        product = session.scalar(select(Product).where(
            Product.business_id == business_id, Product.sku == sku))
        if product is None:
            raise DomainError(f"Product {sku} not found", 404)
        session.add(PurchaseOrderLine(business_id=business_id, purchase_order_id=order.id,
                                      product_id=product.id, ordered_quantity=quantity,
                                      received_quantity=0))
    session.flush()
    return order


def receive_purchase_line(session: Session, business_id: int, order_id: int,
                          line_id: int, quantity: int, actor_id: int) -> PurchaseOrder:
    if not 1 <= quantity <= 1_000_000:
        raise DomainError("Receipt quantity must be 1–1,000,000")
    order = session.scalar(select(PurchaseOrder).where(
        PurchaseOrder.id == order_id, PurchaseOrder.business_id == business_id))
    if order is None:
        raise DomainError("Purchase order not found", 404)
    if order.status not in {"ordered", "partial"}:
        raise DomainError("This purchase order no longer accepts receipts", 409)
    line = session.scalar(select(PurchaseOrderLine).where(
        PurchaseOrderLine.id == line_id, PurchaseOrderLine.business_id == business_id,
        PurchaseOrderLine.purchase_order_id == order.id))
    if line is None:
        raise DomainError("Purchase order line not found", 404)
    product = session.scalar(select(Product).where(
        Product.id == line.product_id, Product.business_id == business_id))
    if product is None:
        raise DomainError("Purchase product not found", 404)
    result = session.execute(update(PurchaseOrderLine).where(
        PurchaseOrderLine.id == line.id, PurchaseOrderLine.business_id == business_id,
        PurchaseOrderLine.received_quantity + quantity <= PurchaseOrderLine.ordered_quantity
    ).values(received_quantity=PurchaseOrderLine.received_quantity + quantity))
    if result.rowcount != 1:
        raise DomainError("Receipt exceeds outstanding purchase quantity", 409)
    apply_stock_delta(session, business_id, order.warehouse_id, product.sku,
                      quantity, "purchase_receipt", f"Purchase order {order.reference}", actor_id)
    session.flush()
    all_received = session.scalars(select(PurchaseOrderLine).where(
        PurchaseOrderLine.business_id == business_id,
        PurchaseOrderLine.purchase_order_id == order_id)).all()
    # ORM identity map reflects the conditional UPDATE in this same session.
    order.status = "received" if all(
        item.received_quantity == item.ordered_quantity for item in all_received
    ) else "partial"
    session.flush()
    return order


def cancel_purchase_order(session: Session, business_id: int, order_id: int) -> PurchaseOrder:
    order = session.scalar(select(PurchaseOrder).where(
        PurchaseOrder.id == order_id, PurchaseOrder.business_id == business_id))
    if order is None:
        raise DomainError("Purchase order not found", 404)
    if order.status not in {"ordered", "partial"}:
        raise DomainError("This purchase order cannot be cancelled", 409)
    # Already-received inventory remains physically present and is not reversed.
    order.status = "cancelled"
    session.flush()
    return order


def list_purchase_orders(session: Session, business_id: int) -> list[dict]:
    orders = session.scalars(select(PurchaseOrder).where(
        PurchaseOrder.business_id == business_id).order_by(PurchaseOrder.id.desc())).all()
    results = []
    for order in orders:
        supplier_name = session.scalar(select(Supplier.name).where(
            Supplier.id == order.supplier_id, Supplier.business_id == business_id))
        warehouse_name = session.scalar(select(Warehouse.name).where(
            Warehouse.id == order.warehouse_id, Warehouse.business_id == business_id))
        lines = session.execute(select(PurchaseOrderLine, Product.sku).join(
            Product, Product.id == PurchaseOrderLine.product_id).where(
            PurchaseOrderLine.business_id == business_id,
            Product.business_id == business_id,
            PurchaseOrderLine.purchase_order_id == order.id).order_by(PurchaseOrderLine.id)).all()
        results.append({"id": order.id, "reference": order.reference,
                        "supplier": supplier_name, "warehouse": warehouse_name,
                        "warehouse_id": order.warehouse_id, "supplier_id": order.supplier_id,
                        "status": order.status, "expected_date": order.expected_date,
                        "items": [{"line_id": line.id, "sku": sku,
                                   "ordered": line.ordered_quantity,
                                   "received": line.received_quantity,
                                   "outstanding": line.ordered_quantity - line.received_quantity}
                                  for line, sku in lines]})
    return results
