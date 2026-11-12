"""Physical cycle counts with stale-snapshot and reservation protection."""
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .errors import DomainError
from .inventory_service import get_stock
from .models import CycleCount, Product, StockLevel, StockMovement, Warehouse, utcnow


def start_count(session: Session, business_id: int, warehouse_id: int,
                sku: str, actor_id: int, note: str = "") -> CycleCount:
    if len(note or "") > 250:
        raise DomainError("Count note is too long")
    product, stock = get_stock(session, business_id, warehouse_id, sku)
    count = CycleCount(business_id=business_id, warehouse_id=warehouse_id,
        product_id=product.id, expected_on_hand=stock.on_hand,
        status="open", created_by=actor_id, note=(note or "").strip())
    session.add(count)
    session.flush()
    return count


def post_count(session: Session, business_id: int, count_id: int,
               counted_on_hand: int, actor_id: int) -> CycleCount:
    if type(counted_on_hand) is not int or not 0 <= counted_on_hand <= 10_000_000:
        raise DomainError("Counted units must be between 0 and 10,000,000")
    count = session.scalar(select(CycleCount).where(
        CycleCount.id == count_id, CycleCount.business_id == business_id))
    if count is None:
        raise DomainError("Cycle count not found", 404)
    if count.status != "open":
        raise DomainError("Cycle count has already been closed", 409)
    stock = session.scalar(select(StockLevel).where(
        StockLevel.business_id == business_id,
        StockLevel.warehouse_id == count.warehouse_id,
        StockLevel.product_id == count.product_id))
    if stock is None:
        raise DomainError("Stock record missing", 409)
    difference = counted_on_hand - count.expected_on_hand
    # Conditional updates avoid overwriting stock changed since this count started.
    result = session.execute(update(CycleCount).where(
        CycleCount.id == count.id, CycleCount.business_id == business_id,
        CycleCount.status == "open").values(
            status="posted", counted_on_hand=counted_on_hand,
            posted_by=actor_id, posted_at=utcnow()))
    if result.rowcount != 1:
        raise DomainError("Cycle count has already been posted", 409)
    result = session.execute(update(StockLevel).where(
        StockLevel.id == stock.id, StockLevel.business_id == business_id,
        StockLevel.on_hand == count.expected_on_hand,
        StockLevel.reserved <= counted_on_hand).values(on_hand=counted_on_hand))
    if result.rowcount != 1:
        raise DomainError("Inventory changed or reserved stock exceeds counted stock; recount required", 409)
    session.add(StockMovement(business_id=business_id,
        warehouse_id=count.warehouse_id, product_id=count.product_id,
        user_id=actor_id, kind="cycle_count", on_hand_delta=difference,
        reserved_delta=0, note=f"Cycle count #{count.id}: {count.note}"[:250]))
    session.flush()
    return count


def cancel_count(session: Session, business_id: int, count_id: int) -> CycleCount:
    count = session.scalar(select(CycleCount).where(
        CycleCount.id == count_id, CycleCount.business_id == business_id))
    if count is None:
        raise DomainError("Cycle count not found", 404)
    result = session.execute(update(CycleCount).where(
        CycleCount.id == count.id, CycleCount.business_id == business_id,
        CycleCount.status == "open").values(status="canceled"))
    if result.rowcount != 1:
        raise DomainError("Only open counts can be canceled", 409)
    session.refresh(count)
    return count


def list_counts(session: Session, business_id: int) -> list[dict]:
    data = session.execute(select(CycleCount, Product.sku, Warehouse.name).join(
        Product, Product.id == CycleCount.product_id).join(
        Warehouse, Warehouse.id == CycleCount.warehouse_id).where(
        CycleCount.business_id == business_id, Product.business_id == business_id,
        Warehouse.business_id == business_id).order_by(CycleCount.id.desc()).limit(100)).all()
    return [{"id": c.id, "sku": sku, "warehouse": warehouse,
             "warehouse_id": c.warehouse_id, "status": c.status,
             "expected_on_hand": c.expected_on_hand,
             "counted_on_hand": c.counted_on_hand,
             "difference": None if c.counted_on_hand is None else c.counted_on_hand-c.expected_on_hand,
             "note": c.note, "created_at": c.created_at.isoformat()} for c, sku, warehouse in data]
