"""Multi-tenant warehouse data model. All business records carry business_id."""
from datetime import datetime, timezone
from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Business(Base):
    __tablename__ = "businesses"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("business_id", "email"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="owner", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Warehouse(Base):
    __tablename__ = "warehouses"
    __table_args__ = (UniqueConstraint("business_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(120), default="", nullable=False)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("business_id", "sku"),
        CheckConstraint("reorder_point >= 0", name="product_reorder_nonnegative"),
        CheckConstraint("price_cents >= 0", name="product_price_nonnegative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True, nullable=False)
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), default="each", nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_point: Mapped[int] = mapped_column(Integer, default=5, nullable=False)


class StockLevel(Base):
    __tablename__ = "stock_levels"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id"),
        CheckConstraint("on_hand >= 0", name="stock_on_hand_nonnegative"),
        CheckConstraint("reserved >= 0 AND reserved <= on_hand", name="stock_reserved_within_hand"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    on_hand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    on_hand_delta: Mapped[int] = mapped_column(Integer, default=0)
    reserved_delta: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(250), default="")
    transfer_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_transfers.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("business_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(254), default="")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (UniqueConstraint("business_id", "reference"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    reference: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ordered")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        CheckConstraint("ordered_quantity > 0", name="purchase_order_quantity_positive"),
        CheckConstraint("received_quantity >= 0 AND received_quantity <= ordered_quantity",
                        name="purchase_order_received_within_ordered"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    ordered_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CustomerOrder(Base):
    __tablename__ = "customer_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    due_date: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="reserved", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OrderLine(Base):
    __tablename__ = "order_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="order_line_positive"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("customer_orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class InventoryTransfer(Base):
    """Warehouse-to-warehouse stock movement; one record per completed transfer."""
    __tablename__ = "inventory_transfers"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="transfer_quantity_positive"),
        UniqueConstraint("business_id", "idempotency_key", name="uq_inventory_transfers_tenant_key"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    source_warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    destination_warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CycleCount(Base):
    """Physical stock count snapshot; posting adjusts the warehouse aggregate."""
    __tablename__ = "cycle_counts"
    __table_args__ = (
        CheckConstraint("expected_on_hand >= 0", name="count_expected_nonnegative"),
        CheckConstraint("counted_on_hand IS NULL OR counted_on_hand >= 0",
                        name="count_observed_nonnegative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    expected_on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    counted_on_hand: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    note: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    posted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReturnReceipt(Base):
    """Idempotency reference and quantity audit for a restocked customer return."""
    __tablename__ = "return_receipts"
    __table_args__ = (
        UniqueConstraint("business_id", "reference"),
        CheckConstraint("quantity > 0", name="return_quantity_positive"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    customer_order_id: Mapped[int] = mapped_column(ForeignKey("customer_orders.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    reference: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StaffInvitation(Base):
    """Expiring, single-use invitation; only a token hash is persisted."""
    __tablename__ = "staff_invitations"
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WarehouseBin(Base):
    """Physical location inside one warehouse (not an inventory accounting record)."""
    __tablename__ = "warehouse_bins"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "code", name="uq_warehouse_bin_code"),
        CheckConstraint("capacity_units IS NULL OR capacity_units > 0", name="bin_capacity_positive"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    zone: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    aisle: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    rack: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    shelf: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    capacity_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BinStock(Base):
    """Warehouse stock placed in a specific bin; subset of StockLevel.on_hand."""
    __tablename__ = "bin_stocks"
    __table_args__ = (
        UniqueConstraint("bin_id", "product_id", name="uq_bin_product"),
        CheckConstraint("on_hand >= 0", name="bin_stock_on_hand_nonnegative"),
        CheckConstraint("allocated >= 0 AND allocated <= on_hand", name="bin_stock_allocated_within_hand"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    bin_id: Mapped[int] = mapped_column(ForeignKey("warehouse_bins.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    on_hand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    allocated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WarehouseTask(Base):
    """Guided putaway / relocation task with explicit work status."""
    __tablename__ = "warehouse_tasks"
    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key", name="uq_warehouse_task_key"),
        CheckConstraint("quantity > 0", name="warehouse_task_qty_positive"),
        CheckConstraint("priority BETWEEN 1 AND 5", name="warehouse_task_priority_range"),
        CheckConstraint("kind IN ('putaway', 'move', 'unlocate')", name="warehouse_task_kind_valid"),
        CheckConstraint("(kind = 'putaway' AND from_bin_id IS NULL AND to_bin_id IS NOT NULL) "
                        "OR (kind = 'move' AND from_bin_id IS NOT NULL AND to_bin_id IS NOT NULL "
                        "AND from_bin_id <> to_bin_id) "
                        "OR (kind = 'unlocate' AND from_bin_id IS NOT NULL AND to_bin_id IS NULL)",
                        name="warehouse_task_locations_valid"),
        CheckConstraint("status IN ('queued', 'assigned', 'in_progress', 'completed', 'canceled')",
                        name="warehouse_task_status_valid"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    from_bin_id: Mapped[int | None] = mapped_column(ForeignKey("warehouse_bins.id"), nullable=True)
    to_bin_id: Mapped[int | None] = mapped_column(ForeignKey("warehouse_bins.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    note: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    completed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    scan_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WarehouseTaskEvent(Base):
    """Append-only accepted workflow transition history."""
    __tablename__ = "warehouse_task_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("warehouse_tasks.id"), nullable=False, index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
