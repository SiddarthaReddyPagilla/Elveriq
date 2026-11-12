"""Transparent reorder suggestions, accounting for open supplier purchase orders.

This is a rule-based planning aid, not a demand forecast or automatic purchase.
"""
from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.orm import Session
from .inventory_service import list_inventory
from .models import PurchaseOrder, PurchaseOrderLine, Product


def reorder_recommendations(session: Session, business_id: int) -> list[dict]:
    incoming: dict[tuple[int, int], int] = defaultdict(int)
    rows = session.execute(select(PurchaseOrder.warehouse_id,
        Product.sku, PurchaseOrderLine.ordered_quantity,
        PurchaseOrderLine.received_quantity).join(
        PurchaseOrderLine, PurchaseOrderLine.purchase_order_id == PurchaseOrder.id).join(
        Product, Product.id == PurchaseOrderLine.product_id).where(
        PurchaseOrder.business_id == business_id,
        PurchaseOrderLine.business_id == business_id,
        Product.business_id == business_id,
        PurchaseOrder.status.in_(("ordered", "partial")))).all()
    for warehouse_id, sku, ordered, received in rows:
        incoming[(warehouse_id, sku)] += ordered - received
    suggestions = []
    for stock in list_inventory(session, business_id):
        reorder_point = stock["reorder_point"]
        if reorder_point <= 0 or stock["available"] > reorder_point:
            continue
        outstanding = incoming[(stock["warehouse_id"], stock["sku"])]
        suggested = max(0, 2 * reorder_point - stock["available"] - outstanding)
        suggestions.append({"warehouse_id": stock["warehouse_id"],
            "warehouse": stock["warehouse"], "sku": stock["sku"],
            "product": stock["name"], "available": stock["available"],
            "reorder_point": reorder_point, "incoming": outstanding,
            "suggested_quantity": suggested,
            "needs_attention": suggested > 0})
    return sorted(suggestions, key=lambda row: (-row["suggested_quantity"],
                                                  row["warehouse"], row["sku"]))
