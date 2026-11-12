"""Pick-list preparation for reserved customer orders (no inventory mutation)."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from .errors import DomainError
from .models import CustomerOrder, OrderLine, Product, Warehouse


def order_pick_list(session: Session, business_id: int, order_id: int) -> dict:
    order = session.scalar(select(CustomerOrder).where(
        CustomerOrder.business_id == business_id, CustomerOrder.id == order_id))
    if order is None:
        raise DomainError("Order not found", 404)
    warehouse = session.scalar(select(Warehouse).where(
        Warehouse.business_id == business_id, Warehouse.id == order.warehouse_id))
    lines = session.execute(select(OrderLine, Product).join(
        Product, Product.id == OrderLine.product_id).where(
        OrderLine.business_id == business_id, Product.business_id == business_id,
        OrderLine.order_id == order_id).order_by(Product.sku)).all()
    return {"order_id": order.id, "customer": order.customer_name,
            "warehouse": warehouse.name, "due_date": order.due_date,
            "status": order.status, "items": [
                {"sku": product.sku, "name": product.name, "unit": product.unit,
                 "quantity": line.quantity} for line, product in lines]}
