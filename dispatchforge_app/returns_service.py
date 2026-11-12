"""Record physically inspected customer returns and restock only fulfilled units.

Each receipt uses a unique business reference to make duplicate submissions visible.
"""
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .errors import DomainError
from .inventory_service import apply_stock_delta, clean_text
from .models import CustomerOrder, OrderLine, Product, ReturnReceipt


def restock_return(session: Session, business_id: int, order_id: int,
                   sku: str, quantity: int, reference: str,
                   actor_id: int, reason: str = "") -> ReturnReceipt:
    reference = clean_text(reference, "Return reference", 100)
    if type(quantity) is not int or not 1 <= quantity <= 1_000_000:
        raise DomainError("Return quantity must be between 1 and 1,000,000")
    if len(reason or "") > 250:
        raise DomainError("Return reason is too long")
    if session.scalar(select(ReturnReceipt.id).where(
        ReturnReceipt.business_id == business_id,
        ReturnReceipt.reference == reference)):
        raise DomainError("Return reference has already been used", 409)
    # Serialize competing returns for the same order in PostgreSQL.
    order = session.scalar(select(CustomerOrder).where(
        CustomerOrder.id == order_id,
        CustomerOrder.business_id == business_id).with_for_update())
    if order is None:
        raise DomainError("Customer order not found", 404)
    if order.status != "fulfilled":
        raise DomainError("Only fulfilled orders can be restocked", 409)
    product = session.scalar(select(Product).where(
        Product.business_id == business_id, Product.sku == sku.strip().upper()))
    if product is None:
        raise DomainError("Product not found", 404)
    line = session.scalar(select(OrderLine).where(
        OrderLine.business_id == business_id, OrderLine.order_id == order.id,
        OrderLine.product_id == product.id))
    if line is None:
        raise DomainError("Product is not part of this order", 404)
    returned = session.scalar(select(func.coalesce(func.sum(ReturnReceipt.quantity), 0)).where(
        ReturnReceipt.business_id == business_id,
        ReturnReceipt.customer_order_id == order.id,
        ReturnReceipt.product_id == product.id)) or 0
    if returned + quantity > line.quantity:
        raise DomainError("Return exceeds quantity originally fulfilled", 409)
    # This endpoint assumes physical receipt and inspection have occurred.
    apply_stock_delta(session, business_id, order.warehouse_id, product.sku,
                      quantity, "customer_return", f"Return {reference}: {reason}"[:250], actor_id)
    receipt = ReturnReceipt(business_id=business_id, customer_order_id=order.id,
        warehouse_id=order.warehouse_id, product_id=product.id,
        quantity=quantity, reference=reference, reason=reason.strip(), user_id=actor_id)
    session.add(receipt)
    session.flush()
    return receipt


def list_returns(session: Session, business_id: int) -> list[dict]:
    data = session.execute(select(ReturnReceipt, Product.sku).join(
        Product, Product.id == ReturnReceipt.product_id).where(
        ReturnReceipt.business_id == business_id, Product.business_id == business_id)
        .order_by(ReturnReceipt.id.desc()).limit(100)).all()
    return [{"id": receipt.id, "reference": receipt.reference,
             "order_id": receipt.customer_order_id, "warehouse_id": receipt.warehouse_id,
             "sku": sku, "quantity": receipt.quantity, "reason": receipt.reason,
             "created_at": receipt.created_at.isoformat()}
            for receipt, sku in data]
