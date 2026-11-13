"""Scheduled customer orders: reserve now, fulfill or release later."""
from datetime import date
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .errors import DomainError
from .inventory_service import clean_text, get_stock
from .warehouse_execution import protected_units_expr
from .models import CustomerOrder, OrderLine, Product, StockLevel, StockMovement, Warehouse


def create_order(session: Session, business_id: int, warehouse_id: int, customer_name: str,
                 due_date: str, items: list[dict], user_id: int | None = None) -> CustomerOrder:
    customer_name = clean_text(customer_name, "Customer name", 150)
    try:
        requested_date = date.fromisoformat(due_date)
    except (TypeError, ValueError):
        raise DomainError("Fulfillment date must use YYYY-MM-DD") from None
    if requested_date < date.today():
        raise DomainError("Fulfillment date cannot be in the past")
    if not session.scalar(select(Warehouse.id).where(Warehouse.id == warehouse_id,
                                                      Warehouse.business_id == business_id)):
        raise DomainError("Warehouse not found", 404)
    if not items or len(items) > 100:
        raise DomainError("An order needs between 1 and 100 line items")
    quantities: dict[str, int] = {}
    for item in items:
        sku = str(item.get("sku", "")).strip().upper()
        quantity = item.get("quantity")
        if not sku or type(quantity) is not int or quantity <= 0 or quantity > 1_000_000:
            raise DomainError("Order items require a SKU and positive integer quantity")
        quantities[sku] = quantities.get(sku, 0) + quantity
        if quantities[sku] > 1_000_000:
            raise DomainError("Combined quantity for a SKU is too high")

    # All writes share one database transaction. The route commits only on full success.
    order = CustomerOrder(business_id=business_id, warehouse_id=warehouse_id,
                          customer_name=customer_name, due_date=requested_date.isoformat())
    session.add(order)
    session.flush()
    for sku in sorted(quantities):
        quantity = quantities[sku]
        product, stock = get_stock(session, business_id, warehouse_id, sku)
        result = session.execute(
            update(StockLevel).where(StockLevel.id == stock.id,
                                     StockLevel.business_id == business_id,
                                     StockLevel.on_hand - StockLevel.reserved >= quantity)
            .values(reserved=StockLevel.reserved + quantity)
        )
        if result.rowcount != 1:
            raise DomainError(f"Insufficient available stock for {sku}", 409)
        session.add(OrderLine(business_id=business_id, order_id=order.id,
                              product_id=product.id, quantity=quantity))
        session.add(StockMovement(business_id=business_id, warehouse_id=warehouse_id,
                                  product_id=product.id, user_id=user_id, kind="reserve",
                                  reserved_delta=quantity, note=f"Order #{order.id}"))
    session.flush()
    return order


def change_order_status(session: Session, business_id: int, order_id: int,
                        action: str, user_id: int | None = None) -> CustomerOrder:
    if action not in {"fulfill", "cancel"}:
        raise DomainError("Unsupported order action")
    order = session.scalar(select(CustomerOrder).where(CustomerOrder.id == order_id,
                                                       CustomerOrder.business_id == business_id))
    if order is None:
        raise DomainError("Order not found", 404)
    if order.status != "reserved":
        raise DomainError("Only reserved orders can be fulfilled or canceled", 409)
    for line in session.scalars(select(OrderLine).where(OrderLine.order_id == order.id,
                                                        OrderLine.business_id == business_id)):
        stock = session.scalar(select(StockLevel).where(
            StockLevel.business_id == business_id,
            StockLevel.warehouse_id == order.warehouse_id,
            StockLevel.product_id == line.product_id))
        if stock is None:
            raise DomainError("Inventory record is missing", 409)
        values = {"reserved": StockLevel.reserved - line.quantity}
        hand_delta = 0
        if action == "fulfill":
            values["on_hand"] = StockLevel.on_hand - line.quantity
            hand_delta = -line.quantity
        result = session.execute(
            update(StockLevel).where(StockLevel.id == stock.id,
                                     StockLevel.business_id == business_id,
                                     StockLevel.reserved >= line.quantity,
                                     *( [StockLevel.on_hand - line.quantity >= protected_units_expr()]
                                        if action == "fulfill" else []))
            .values(**values)
        )
        if result.rowcount != 1:
            raise DomainError("Reserved stock is insufficient or still physically placed in a bin; move it to unlocated stock before fulfillment", 409)
        session.add(StockMovement(business_id=business_id, warehouse_id=order.warehouse_id,
                                  product_id=line.product_id, user_id=user_id,
                                  kind=action, on_hand_delta=hand_delta,
                                  reserved_delta=-line.quantity, note=f"Order #{order.id}"))
    order.status = "fulfilled" if action == "fulfill" else "canceled"
    session.flush()
    return order


def list_orders(session: Session, business_id: int) -> list[dict]:
    orders = session.scalars(select(CustomerOrder).where(CustomerOrder.business_id == business_id)
                             .order_by(CustomerOrder.id.desc()).limit(100)).all()
    if not orders:
        return []
    ids = [order.id for order in orders]
    lines = session.execute(select(OrderLine, Product.sku).join(Product, Product.id == OrderLine.product_id)
                            .where(OrderLine.business_id == business_id,
                                   OrderLine.order_id.in_(ids))).all()
    grouped: dict[int, list[dict]] = {id: [] for id in ids}
    for line, sku in lines:
        grouped[line.order_id].append({"sku": sku, "quantity": line.quantity})
    return [{"id": o.id, "warehouse_id": o.warehouse_id, "customer_name": o.customer_name,
             "due_date": o.due_date, "status": o.status, "items": grouped[o.id],
             "created_at": o.created_at.isoformat()} for o in orders]
