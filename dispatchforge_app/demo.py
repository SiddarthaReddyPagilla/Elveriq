"""Public, clearly fictional, read-only demo warehouse with example data."""
from datetime import date, timedelta
from sqlalchemy import select
from .models import Business, Supplier
from .inventory_service import create_warehouse, create_product, apply_stock_delta, create_supplier
from .order_service import create_order
from .purchasing_service import create_purchase_order

DEMO_SLUG = "sample-workspace"


def seed_demo(db):
    with db.SessionLocal() as session:
        if session.scalar(select(Business.id).where(Business.slug == DEMO_SLUG)):
            return
        business = Business(name="Denton Sample Distribution (Fictional)", slug=DEMO_SLUG)
        session.add(business)
        session.flush()
        central = create_warehouse(session, business.id, "Denton Central", "Denton, TX")
        north = create_warehouse(session, business.id, "North Denton Storage", "Denton, TX")
        create_supplier(session, business.id, "North Texas Wholesale (Fictional)", "")
        create_supplier(session, business.id, "Sample Packaging Co. (Fictional)", "")
        examples = [
            ("WATER-500ML", "Bottled Water 500 ml", 149, 20, 150, 50),
            ("SNACK-001", "Trail Mix Packs", 399, 15, 65, 20),
            ("BOX-001", "Shipping Boxes, Small", 225, 40, 100, 80),
            ("TAPE-001", "Packing Tape Rolls", 349, 20, 12, 8),
            ("SOAP-001", "Hand Soap 12 oz", 550, 12, 40, 22),
            ("BAG-001", "Reusable Shopping Bags", 275, 10, 8, 4),
            ("GLOVES-001", "Work Gloves", 899, 10, 42, 12),
        ]
        for sku, name, price, reorder, central_qty, north_qty in examples:
            create_product(session, business.id, sku, name, price, reorder)
            apply_stock_delta(session, business.id, central.id, sku, central_qty, "receive", "Initial fictional stock")
            apply_stock_delta(session, business.id, north.id, sku, north_qty, "receive", "Initial fictional stock")
        create_order(session, business.id, central.id, "Denton Retail Sample",
                     (date.today() + timedelta(days=3)).isoformat(),
                     [{"sku": "WATER-500ML", "quantity": 24}, {"sku": "SNACK-001", "quantity": 6}])
        supplier = session.scalar(select(Supplier).where(
            Supplier.business_id == business.id,
            Supplier.name == "North Texas Wholesale (Fictional)"))
        create_purchase_order(session, business.id, supplier.id, central.id,
                              (date.today() + timedelta(days=4)).isoformat(),
                              "SAMPLE-PO-001", [{"sku": "SOAP-001", "quantity": 60}])
        session.commit()
