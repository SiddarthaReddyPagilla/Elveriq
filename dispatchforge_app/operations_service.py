"""Upcoming fulfillment and supplier receiving workload for each workspace."""
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import CustomerOrder, PurchaseOrder


def operations_queue(session: Session, business_id: int, days: int = 7) -> dict:
    if not 1 <= days <= 90:
        raise ValueError("days outside supported range")
    today = date.today().isoformat()
    horizon = (date.today() + timedelta(days=days)).isoformat()
    orders = session.scalars(select(CustomerOrder).where(
        CustomerOrder.business_id == business_id,
        CustomerOrder.status == "reserved").order_by(
        CustomerOrder.due_date, CustomerOrder.id).limit(500)).all()
    pending = session.scalars(select(PurchaseOrder).where(
        PurchaseOrder.business_id == business_id,
        PurchaseOrder.status.in_(("ordered", "partial"))).order_by(
        PurchaseOrder.expected_date, PurchaseOrder.id).limit(500)).all()
    outgoing = [{"id": o.id, "customer": o.customer_name,
                 "due_date": o.due_date, "warehouse_id": o.warehouse_id,
                 "overdue": o.due_date < today}
                for o in orders if o.due_date <= horizon]
    incoming = [{"id": o.id, "reference": o.reference,
                 "expected_date": o.expected_date,
                 "warehouse_id": o.warehouse_id, "status": o.status,
                 "overdue": o.expected_date is not None and o.expected_date < today}
                for o in pending if o.expected_date is None or o.expected_date <= horizon]
    return {"as_of": today, "days": days, "outgoing_orders": outgoing,
            "incoming_purchases": incoming,
            "overdue_outgoing": sum(item["overdue"] for item in outgoing),
            "overdue_incoming": sum(item["overdue"] for item in incoming)}
