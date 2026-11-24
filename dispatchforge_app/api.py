"""JSON API for the warehouse SaaS demo and authenticated workspaces."""
from datetime import date
import csv
import io
from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .auth import actor_from_session, check_csrf, require_role
from .demo import DEMO_SLUG
from .errors import DomainError
from .inventory_service import (apply_stock_delta, create_product, create_supplier,
                                create_warehouse, list_inventory, list_movements)
from .models import Business, CustomerOrder, OrderLine, OutboundPick, Product, Supplier, Warehouse
from .order_service import create_order, change_order_status, list_orders
from .purchasing_service import (create_purchase_order, receive_purchase_line,
    cancel_purchase_order, list_purchase_orders)

from .transfer_service import transfer_stock, list_transfers
from .picking_service import order_pick_list
from .replenishment_service import reorder_recommendations
from .cycle_count_service import start_count, post_count, cancel_count, list_counts
from .returns_service import restock_return, list_returns
from .staff_service import (create_invitation, accept_invitation, staff_members, change_staff_role)
from .audit_service import audit_stock
from .operations_service import operations_queue
from .bin_cycle_count_service import (start_bin_count, post_bin_count,
    cancel_bin_count, list_bin_counts)
from .outbound_service import (plan_pick, list_picks, pick_events, claim_pick, start_pick,
    scan_pick, cancel_pick, create_carton, pack_pick, seal_carton, list_cartons,
    dispatch_order, list_shipments, _order)
from .warehouse_execution import (create_bin, list_bins, list_bin_stock, location_summary,
    create_task, list_tasks, task_events, assign_task, claim_task, start_task,
    cancel_task, complete_task)

from .inbound_service import (create_notice, arrive_notice, scan_receipt, close_notice,
    cancel_notice, list_notices, receipt_history, notice_events)

from .exception_service import (open_case,list_cases,assign_case,acknowledge_case,
    resolve_case,reopen_case,comment_case,case_history)

from .shipment_tracking import (record_milestone,shipment_timeline,shipment_overview)

from .operations_metrics import operational_metrics

router = APIRouter(prefix="/api")


def get_db(request: Request):
    with request.app.state.db.SessionLocal() as session:
        yield session


def read_access(request: Request, session: Session, demo: bool):
    if demo:
        business = session.scalar(select(Business).where(Business.slug == DEMO_SLUG))
        if not business:
            raise DomainError("Sample workspace is unavailable", 503)
        return business.id
    actor = actor_from_session(session, request.session)
    if actor is None:
        raise DomainError("Sign in to see your workspace", 401)
    return actor.business_id


def write_access(request: Request, session: Session, csrf: str, owner_only: bool = False):
    actor = actor_from_session(session, request.session)
    require_role(actor, {"owner"} if owner_only else {"owner", "manager", "staff"})
    check_csrf(request, csrf)
    return actor


class WarehouseIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    city: str = Field(default="", max_length=120)


class ProductIn(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=180)
    price_cents: int = Field(default=0, ge=0, le=100_000_000)
    reorder_point: int = Field(default=5, ge=0, le=1_000_000)
    unit: str = Field(default="each", max_length=24)


class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    email: str = Field(default="", max_length=254)


class StockIn(BaseModel):
    warehouse_id: int
    sku: str
    quantity: int = Field(ge=1, le=1_000_000)
    note: str = Field(default="", max_length=250)


class AdjustIn(BaseModel):
    warehouse_id: int
    sku: str
    delta: int = Field(ge=-1_000_000, le=1_000_000)
    note: str = Field(default="", max_length=250)


class StaffInviteIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: str


class StaffAcceptIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=10, max_length=128)


class StaffRoleIn(BaseModel):
    role: str


class ReturnIn(BaseModel):
    order_id: int
    sku: str = Field(min_length=1, max_length=80)
    quantity: int = Field(ge=1, le=1_000_000)
    reference: str = Field(min_length=1, max_length=100)
    reason: str = Field(default="", max_length=250)


class CountStartIn(BaseModel):
    warehouse_id: int
    sku: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=250)


class CountPostIn(BaseModel):
    counted_on_hand: int = Field(ge=0, le=10_000_000)


class TransferIn(BaseModel):
    source_warehouse_id: int
    destination_warehouse_id: int
    sku: str = Field(min_length=1, max_length=80)
    quantity: int = Field(ge=1, le=1_000_000)
    note: str = Field(default="", max_length=250)


class BinIn(BaseModel):
    warehouse_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=64)
    zone: str = Field(default="", max_length=60)
    aisle: str = Field(default="", max_length=40)
    rack: str = Field(default="", max_length=40)
    shelf: str = Field(default="", max_length=40)
    capacity_units: int | None = Field(default=None, ge=1, le=10_000_000)


class BinCountStartIn(BaseModel):
    warehouse_id: int = Field(gt=0)
    bin_id: int = Field(gt=0)
    sku: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=250)


class TaskIn(BaseModel):
    warehouse_id: int = Field(gt=0)
    sku: str = Field(min_length=1, max_length=80)
    kind: str
    to_bin_id: int | None = Field(default=None, gt=0)
    from_bin_id: int | None = Field(default=None, gt=0)
    quantity: int = Field(ge=1, le=1_000_000)
    priority: int = Field(default=3, ge=1, le=5)
    note: str = Field(default="", max_length=250)
    assigned_user_id: int | None = Field(default=None, gt=0)


class TaskAssignIn(BaseModel):
    assigned_user_id: int | None = Field(default=None, gt=0)


class TaskScanIn(BaseModel):
    scan_sku: str = Field(min_length=1, max_length=80)
    scan_to_bin: str = Field(min_length=1, max_length=64)
    scan_from_bin: str | None = Field(default=None, max_length=64)




class OutboundPickIn(BaseModel):
    order_line_id: int = Field(gt=0)
    bin_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=1_000_000)


class OutboundScanIn(BaseModel):
    scan_sku: str = Field(min_length=1, max_length=80)
    scan_bin: str = Field(min_length=1, max_length=64)


class CartonCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class CartonPackIn(BaseModel):
    pick_id: int = Field(gt=0)
    scan_sku: str = Field(min_length=1, max_length=80)
    scan_carton: str = Field(min_length=1, max_length=64)


class DispatchIn(BaseModel):
    carrier: str = Field(min_length=1, max_length=80)
    tracking_reference: str = Field(min_length=1, max_length=120)


class OrderItemIn(BaseModel):
    sku: str
    quantity: int = Field(ge=1, le=1_000_000)


class PurchaseItemIn(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    quantity: int = Field(ge=1, le=1_000_000)


class PurchaseIn(BaseModel):
    supplier_id: int
    warehouse_id: int
    reference: str = Field(min_length=1, max_length=100)
    expected_date: date | None = None
    items: list[PurchaseItemIn] = Field(min_length=1, max_length=100)


class PurchaseReceiveIn(BaseModel):
    line_id: int
    quantity: int = Field(ge=1, le=1_000_000)


class OrderIn(BaseModel):
    warehouse_id: int
    customer_name: str = Field(min_length=1, max_length=150)
    due_date: date
    items: list[OrderItemIn] = Field(min_length=1, max_length=100)


@router.get("/overview")
def overview(request: Request, demo: bool = False, session: Session = Depends(get_db)):
    bid = read_access(request, session, demo)
    inventory = list_inventory(session, bid)
    orders = list_orders(session, bid)
    return {
        "business": session.scalar(select(Business.name).where(Business.id == bid)),
        "products": session.scalar(select(func.count(Product.id)).where(Product.business_id == bid)),
        "warehouses": session.scalar(select(func.count(Warehouse.id)).where(Warehouse.business_id == bid)),
        "on_hand": sum(row["on_hand"] for row in inventory),
        "reserved": sum(row["reserved"] for row in inventory),
        "low_stock": sum(row["low_stock"] for row in inventory),
        "open_orders": sum(o["status"] == "reserved" for o in orders),
        "demo": demo,
    }


@router.get("/warehouses")
def warehouses(request: Request, demo: bool = False, session: Session = Depends(get_db)):
    bid = read_access(request, session, demo)
    return [{"id": w.id, "name": w.name, "city": w.city} for w in session.scalars(
        select(Warehouse).where(Warehouse.business_id == bid).order_by(Warehouse.name))]


@router.post("/warehouses", status_code=201)
def add_warehouse(payload: WarehouseIn, request: Request,
                  x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token, owner_only=True)
    w = create_warehouse(session, actor.business_id, payload.name, payload.city)
    session.commit()
    return {"id": w.id, "name": w.name}


@router.get("/products")
def products(request: Request, demo: bool = False, session: Session = Depends(get_db)):
    bid = read_access(request, session, demo)
    return [{"sku": p.sku, "name": p.name, "unit": p.unit,
             "price_cents": p.price_cents, "reorder_point": p.reorder_point}
            for p in session.scalars(select(Product).where(Product.business_id == bid).order_by(Product.name))]


@router.post("/products", status_code=201)
def add_product(payload: ProductIn, request: Request,
                x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token, owner_only=True)
    product = create_product(session, actor.business_id, payload.sku, payload.name,
                             payload.price_cents, payload.reorder_point, payload.unit)
    session.commit()
    return {"id": product.id, "sku": product.sku}


@router.get("/inventory")
def inventory(request: Request, demo: bool = False, session: Session = Depends(get_db)):
    return list_inventory(session, read_access(request, session, demo))


@router.post("/stock/receive")
def receive(payload: StockIn, request: Request,
            x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    stock = apply_stock_delta(session, actor.business_id, payload.warehouse_id,
                              payload.sku, payload.quantity, "receive", payload.note, actor.id)
    session.commit()
    return {"on_hand": stock.on_hand, "reserved": stock.reserved}


@router.post("/stock/adjust")
def adjust(payload: AdjustIn, request: Request,
           x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token, owner_only=True)
    stock = apply_stock_delta(session, actor.business_id, payload.warehouse_id,
                              payload.sku, payload.delta, "adjust", payload.note, actor.id)
    session.commit()
    return {"on_hand": stock.on_hand, "reserved": stock.reserved}


@router.get("/transfers")
def transfers(request: Request, demo: bool = False, session: Session = Depends(get_db)):
    return list_transfers(session, read_access(request, session, demo))


@router.post("/transfers")
def create_transfer(payload: TransferIn, request: Request,
                    idempotency_key: str = Header(min_length=8, max_length=128),
                    x_csrf_token: str = Header(default=""),
                    session: Session = Depends(get_db)):
    try:
        actor = write_access(request, session, x_csrf_token)
        transfer, replayed = transfer_stock(
            session, actor.business_id, payload.source_warehouse_id,
            payload.destination_warehouse_id, payload.sku, payload.quantity,
            payload.note, actor.id, idempotency_key=idempotency_key,
        )
        result = {"id": transfer.id, "quantity": transfer.quantity,
                  "replayed": replayed}
        session.commit()
        return JSONResponse(result, status_code=200 if replayed else 201)
    except Exception:
        session.rollback()  # Never commit a partial debit on an error.
        raise


@router.get("/staff")
def list_staff(request: Request, session: Session = Depends(get_db)):
    actor = actor_from_session(session, request.session)
    require_role(actor, {"owner"})
    return staff_members(session, actor.business_id)


@router.post("/staff/invitations", status_code=201)
def invite_staff(payload: StaffInviteIn, request: Request,
                 x_csrf_token: str = Header(default=""),
                 session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token, owner_only=True)
    invitation, token = create_invitation(session, actor.business_id, payload.email,
                                           payload.role, actor.id)
    session.commit()
    # Return one time: only SHA-256 digest is stored in the database.
    return {"id": invitation.id, "email": invitation.email, "role": invitation.role,
            "token": token, "expires_at": invitation.expires_at.isoformat()}


@router.post("/staff/invitations/accept", status_code=201)
def accept_staff_invite(payload: StaffAcceptIn, session: Session = Depends(get_db)):
    staff = accept_invitation(session, payload.token, payload.password)
    session.commit()
    return {"id": staff.id, "email": staff.email, "role": staff.role}


@router.patch("/staff/{user_id}/role")
def update_staff(user_id: int, payload: StaffRoleIn, request: Request,
                 x_csrf_token: str = Header(default=""),
                 session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token, owner_only=True)
    user = change_staff_role(session, actor.business_id, user_id, payload.role, actor.id)
    session.commit()
    return {"id": user.id, "role": user.role}


@router.get("/returns")
def returns(request: Request, demo: bool = False, session: Session = Depends(get_db)):
    return list_returns(session, read_access(request, session, demo))


@router.post("/returns", status_code=201)
def record_return(payload: ReturnIn, request: Request,
                  x_csrf_token: str = Header(default=""),
                  session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    receipt = restock_return(session, actor.business_id, payload.order_id,
        payload.sku, payload.quantity, payload.reference, actor.id, payload.reason)
    session.commit()
    return {"id": receipt.id, "reference": receipt.reference, "quantity": receipt.quantity}


@router.get("/cycle-counts")
def cycle_counts(request: Request, demo: bool = False,
                 session: Session = Depends(get_db)):
    return list_counts(session, read_access(request, session, demo))


@router.post("/cycle-counts", status_code=201)
def open_cycle_count(payload: CountStartIn, request: Request,
                     x_csrf_token: str = Header(default=""),
                     session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    count = start_count(session, actor.business_id, payload.warehouse_id,
                        payload.sku, actor.id, payload.note)
    session.commit()
    return {"id": count.id, "status": count.status, "expected_on_hand": count.expected_on_hand}


@router.post("/cycle-counts/{count_id}/post")
def reconcile_cycle_count(count_id: int, payload: CountPostIn, request: Request,
                          x_csrf_token: str = Header(default=""),
                          session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token, owner_only=True)
    count = post_count(session, actor.business_id, count_id,
                       payload.counted_on_hand, actor.id)
    session.commit()
    return {"id": count.id, "status": count.status, "counted_on_hand": count.counted_on_hand}


@router.post("/cycle-counts/{count_id}/cancel")
def abandon_cycle_count(count_id: int, request: Request,
                        x_csrf_token: str = Header(default=""),
                        session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token, owner_only=True)
    count = cancel_count(session, actor.business_id, count_id)
    session.commit()
    return {"id": count.id, "status": count.status}


@router.get("/bin-cycle-counts")
def bin_cycle_counts(request: Request, demo: bool = False,
                     session: Session = Depends(get_db)):
    return list_bin_counts(session, read_access(request, session, demo))


@router.post("/bin-cycle-counts", status_code=201)
def open_bin_cycle_count(payload: BinCountStartIn, request: Request,
                         x_csrf_token: str = Header(default=""),
                         session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    count = start_bin_count(session, actor.business_id, payload.warehouse_id,
                            payload.bin_id, payload.sku, actor.id, payload.note)
    session.commit()
    return {"id": count.id, "status": count.status,
            "expected_on_hand": count.expected_on_hand}


@router.post("/bin-cycle-counts/{count_id}/post")
def reconcile_bin_cycle_count(count_id: int, payload: CountPostIn, request: Request,
                              x_csrf_token: str = Header(default=""),
                              session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token, owner_only=True)
    count = post_bin_count(session, actor.business_id, count_id,
                           payload.counted_on_hand, actor.id)
    session.commit()
    return {"id": count.id, "status": count.status,
            "counted_on_hand": count.counted_on_hand,
            "variance": count.counted_on_hand - count.expected_on_hand}


@router.post("/bin-cycle-counts/{count_id}/cancel")
def abandon_bin_cycle_count(count_id: int, request: Request,
                            x_csrf_token: str = Header(default=""),
                            session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token, owner_only=True)
    count = cancel_bin_count(session, actor.business_id, count_id)
    session.commit()
    return {"id": count.id, "status": count.status}


@router.get("/replenishment")
def replenishment(request: Request, demo: bool = False,
                  session: Session = Depends(get_db)):
    return reorder_recommendations(session, read_access(request, session, demo))


@router.get("/export/replenishment.csv")
def export_replenishment(request: Request, demo: bool = False,
                         session: Session = Depends(get_db)):
    rows = reorder_recommendations(session, read_access(request, session, demo))
    stream = io.StringIO()
    writer = csv.writer(stream)
    columns = ["warehouse", "sku", "product", "available", "reorder_point",
               "incoming", "suggested_quantity"]
    writer.writerow(columns)
    for row in rows:
        writer.writerow([csv_cell(row[col]) for col in columns])
    return Response(stream.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="elveriq-replenishment.csv"'})


@router.get("/operations/queue")
def upcoming_operations(request: Request, demo: bool = False,
                        days: int = Query(default=7, ge=1, le=90),
                        session: Session = Depends(get_db)):
    return operations_queue(session, read_access(request, session, demo), days)


@router.get("/audit")
def audit(request: Request, demo: bool = False, kind: str | None = None,
          sku: str | None = None, warehouse_id: int | None = None,
          before_id: int | None = Query(default=None, ge=1),
          limit: int = Query(default=50, ge=1, le=200),
          session: Session = Depends(get_db)):
    return audit_stock(session, read_access(request, session, demo), kind=kind,
        sku=sku, warehouse_id=warehouse_id, before_id=before_id, limit=limit)


@router.get("/movements")
def movements(request: Request, demo: bool = False, session: Session = Depends(get_db)):
    return list_movements(session, read_access(request, session, demo))


@router.get("/suppliers")
def suppliers(request: Request, demo: bool = False, session: Session = Depends(get_db)):
    bid = read_access(request, session, demo)
    return [{"id": s.id, "name": s.name, "email": s.email} for s in session.scalars(
        select(Supplier).where(Supplier.business_id == bid).order_by(Supplier.name))]


@router.post("/suppliers", status_code=201)
def add_supplier(payload: SupplierIn, request: Request,
                 x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token, owner_only=True)
    supplier = create_supplier(session, actor.business_id, payload.name, payload.email)
    session.commit()
    return {"id": supplier.id, "name": supplier.name}


@router.get("/orders")
def orders(request: Request, demo: bool = False, session: Session = Depends(get_db)):
    return list_orders(session, read_access(request, session, demo))


@router.get("/orders/{order_id}/pick-list")
def pick_list(order_id: int, request: Request, session: Session = Depends(get_db)):
    return order_pick_list(session, read_access(request, session, False), order_id)


@router.get("/orders/{order_id}/pick-list.csv")
def export_pick_list(order_id: int, request: Request,
                     session: Session = Depends(get_db)):
    details = order_pick_list(session, read_access(request, session, False), order_id)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["order_id", "customer", "warehouse", "due_date", "sku", "name", "unit", "quantity"])
    for item in details["items"]:
        writer.writerow([csv_cell(details["order_id"]), csv_cell(details["customer"]),
                         csv_cell(details["warehouse"]), csv_cell(details["due_date"]),
                         csv_cell(item["sku"]), csv_cell(item["name"]),
                         csv_cell(item["unit"]), item["quantity"]])
    return Response(stream.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="elveriq-pick-{order_id}.csv"'})


@router.post("/orders", status_code=201)
def add_order(payload: OrderIn, request: Request,
              x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    order = create_order(session, actor.business_id, payload.warehouse_id,
                         payload.customer_name, payload.due_date.isoformat(),
                         [item.model_dump() for item in payload.items], actor.id)
    session.commit()
    return {"id": order.id, "status": order.status}


@router.post("/orders/{order_id}/{action}")
def update_order(order_id: int, action: str, request: Request,
                 x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    order = change_order_status(session, actor.business_id, order_id, action, actor.id)
    session.commit()
    return {"id": order.id, "status": order.status}


@router.get("/purchase-orders")
def purchase_orders(request: Request, demo: bool = False, session: Session = Depends(get_db)):
    return list_purchase_orders(session, read_access(request, session, demo))


@router.post("/purchase-orders", status_code=201)
def add_purchase_order(payload: PurchaseIn, request: Request,
                       x_csrf_token: str = Header(default=""),
                       session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    order = create_purchase_order(session, actor.business_id, payload.supplier_id,
                                  payload.warehouse_id,
                                  payload.expected_date.isoformat() if payload.expected_date else None,
                                  payload.reference,
                                  [item.model_dump() for item in payload.items])
    session.commit()
    return {"id": order.id, "status": order.status}


@router.post("/purchase-orders/{order_id}/receive")
def receive_purchase_order_line(order_id: int, payload: PurchaseReceiveIn, request: Request,
                                x_csrf_token: str = Header(default=""),
                                session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    order = receive_purchase_line(session, actor.business_id, order_id,
                                  payload.line_id, payload.quantity, actor.id)
    session.commit()
    return {"id": order.id, "status": order.status}


@router.post("/purchase-orders/{order_id}/cancel")
def cancel_purchase(order_id: int, request: Request,
                    x_csrf_token: str = Header(default=""),
                    session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    order = cancel_purchase_order(session, actor.business_id, order_id)
    session.commit()
    return {"id": order.id, "status": order.status}


# Warehouse execution phase 1: tenant-scoped bins, stock placement and work tasks.
@router.get("/locations")
def locations(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
              demo: bool = False, session: Session = Depends(get_db)):
    return list_bins(session, read_access(request, session, demo), warehouse_id)


@router.get("/locations/stock")
def location_stock(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
                   demo: bool = False, session: Session = Depends(get_db)):
    return list_bin_stock(session, read_access(request, session, demo), warehouse_id)


@router.get("/locations/reconciliation")
def location_reconciliation(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
                            demo: bool = False, session: Session = Depends(get_db)):
    return location_summary(session, read_access(request, session, demo), warehouse_id)


@router.post("/locations", status_code=201)
def add_location(payload: BinIn, request: Request, x_csrf_token: str = Header(default=""),
                 session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    require_role(actor, {"owner", "manager"})
    bin_row = create_bin(session, actor.business_id, payload.warehouse_id, payload.code,
                         payload.zone, payload.aisle, payload.rack, payload.shelf, payload.capacity_units)
    session.commit()
    return {"id": bin_row.id, "code": bin_row.code, "warehouse_id": bin_row.warehouse_id}


@router.get("/tasks")
def warehouse_tasks(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
                    demo: bool = False, session: Session = Depends(get_db)):
    return list_tasks(session, read_access(request, session, demo), warehouse_id)


@router.get("/tasks/assignees")
def task_assignees(request: Request, session: Session = Depends(get_db)):
    actor = actor_from_session(session, request.session)
    require_role(actor, {"owner", "manager"})
    from .models import User
    return [{"id": u.id, "email": u.email, "role": u.role} for u in session.scalars(
        select(User).where(User.business_id == actor.business_id,
                           User.role.in_(("owner", "manager", "staff"))).order_by(User.email))]


@router.get("/tasks/{task_id}/events")
def warehouse_task_events(task_id: int, request: Request, demo: bool = False,
                          session: Session = Depends(get_db)):
    return task_events(session, read_access(request, session, demo), task_id)


@router.post("/tasks", status_code=201)
def add_task(payload: TaskIn, request: Request, idempotency_key: str = Header(default=""),
             x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    require_role(actor, {"owner", "manager"})
    task, replayed = create_task(session, actor.business_id, payload.warehouse_id,
        payload.sku, payload.kind, payload.to_bin_id, payload.quantity, actor.id,
        payload.from_bin_id, payload.assigned_user_id, payload.priority, payload.note,
        idempotency_key)
    session.commit()
    return {"id": task.id, "status": task.status, "replayed": replayed}


@router.post("/tasks/{task_id}/assign")
def set_task_assignee(task_id: int, payload: TaskAssignIn, request: Request,
                      x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    require_role(actor, {"owner", "manager"})
    task = assign_task(session, actor.business_id, task_id, actor.id, payload.assigned_user_id)
    session.commit()
    return {"id": task.id, "status": task.status, "assigned_user_id": task.assigned_user_id}


@router.post("/tasks/{task_id}/claim")
def claim_work(task_id: int, request: Request, x_csrf_token: str = Header(default=""),
               session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    task = claim_task(session, actor.business_id, task_id, actor.id)
    session.commit()
    return {"id": task.id, "status": task.status}


@router.post("/tasks/{task_id}/start")
def begin_work(task_id: int, request: Request, x_csrf_token: str = Header(default=""),
               session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    task = start_task(session, actor.business_id, task_id, actor.id)
    session.commit()
    return {"id": task.id, "status": task.status}


@router.post("/tasks/{task_id}/complete")
def finish_work(task_id: int, payload: TaskScanIn, request: Request,
                x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    try:
        task, replayed = complete_task(session, actor.business_id, task_id,
            actor.id, payload.scan_sku, payload.scan_to_bin, payload.scan_from_bin)
    except DomainError as error:
        # Save rejected scan audit WITHOUT stock changes: the service only adds
        # an event before raising this exact validation error.
        if error.message.startswith("Scan verification failed"):
            session.commit()
        raise
    session.commit()
    return {"id": task.id, "status": task.status, "replayed": replayed}


@router.post("/tasks/{task_id}/cancel")
def cancel_work(task_id: int, request: Request, x_csrf_token: str = Header(default=""),
                session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    require_role(actor, {"owner", "manager"})
    task = cancel_task(session, actor.business_id, task_id, actor.id)
    session.commit()
    return {"id": task.id, "status": task.status}




@router.get("/outbound/orders/{order_id}/lines")
def outbound_order_lines(order_id: int, request: Request, session: Session = Depends(get_db)):
    bid = read_access(request, session, False)
    order = _order(session, bid, order_id)
    rows = session.execute(select(OrderLine, Product.sku).join(Product, Product.id == OrderLine.product_id)
        .where(OrderLine.business_id == bid, OrderLine.order_id == order.id,
               Product.business_id == bid).order_by(OrderLine.id)).all()
    picks = list_picks(session, bid, order.id)
    return [{"order_line_id": line.id, "sku": sku, "quantity": line.quantity,
             "planned": sum(p["quantity"] for p in picks if p["order_line_id"] == line.id
                            and p["status"] != "canceled"),
             "packed": sum(p["quantity"] for p in picks if p["order_line_id"] == line.id
                           and p["status"] in ("packed", "shipped"))}
            for line, sku in rows]


@router.get("/outbound/picks")
def outbound_picks(request: Request, order_id: int | None = Query(default=None, gt=0),
                   session: Session = Depends(get_db)):
    return list_picks(session, read_access(request, session, False), order_id)


@router.get("/outbound/picks/{pick_id}/events")
def outbound_events(pick_id: int, request: Request, session: Session = Depends(get_db)):
    return pick_events(session, read_access(request, session, False), pick_id)


@router.post("/outbound/orders/{order_id}/picks", status_code=201)
def outbound_plan(order_id: int, payload: OutboundPickIn, request: Request,
                  idempotency_key: str = Header(default=""),
                  x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    require_role(actor, {"owner", "manager"})
    pick, replayed = plan_pick(session, actor.business_id, order_id,
        payload.order_line_id, payload.bin_id, payload.quantity, actor.id, idempotency_key)
    session.commit()
    return {"id": pick.id, "status": pick.status, "replayed": replayed}


@router.post("/outbound/picks/{pick_id}/claim")
def outbound_claim(pick_id: int, request: Request, x_csrf_token: str = Header(default=""),
                   session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    pick = claim_pick(session, actor.business_id, pick_id, actor.id)
    session.commit()
    return {"id": pick.id, "status": pick.status}


@router.post("/outbound/picks/{pick_id}/start")
def outbound_start(pick_id: int, request: Request, x_csrf_token: str = Header(default=""),
                   session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    pick = start_pick(session, actor.business_id, pick_id, actor.id)
    session.commit()
    return {"id": pick.id, "status": pick.status}


@router.post("/outbound/picks/{pick_id}/scan")
def outbound_scan(pick_id: int, payload: OutboundScanIn, request: Request,
                  x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    try:
        pick, replayed = scan_pick(session, actor.business_id, pick_id,
            actor.id, payload.scan_sku, payload.scan_bin)
    except DomainError as error:
        if error.message.startswith("Outbound scan verification failed"):
            session.commit()  # Failed scan audit, never a stock movement.
        raise
    session.commit()
    return {"id": pick.id, "status": pick.status, "replayed": replayed}


@router.post("/outbound/picks/{pick_id}/cancel")
def outbound_cancel(pick_id: int, request: Request,
                    x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    require_role(actor, {"owner", "manager"})
    pick = cancel_pick(session, actor.business_id, pick_id, actor.id)
    session.commit()
    return {"id": pick.id, "status": pick.status}


@router.get("/outbound/cartons")
def outbound_cartons(request: Request, order_id: int | None = Query(default=None, gt=0),
                     session: Session = Depends(get_db)):
    return list_cartons(session, read_access(request, session, False), order_id)


@router.post("/outbound/orders/{order_id}/cartons", status_code=201)
def outbound_create_carton(order_id: int, payload: CartonCreateIn, request: Request,
                           x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    carton = create_carton(session, actor.business_id, order_id, payload.code, actor.id)
    session.commit()
    return {"id": carton.id, "code": carton.code, "status": carton.status}


@router.post("/outbound/cartons/{carton_id}/pack")
def outbound_pack(carton_id: int, payload: CartonPackIn, request: Request,
                  x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    try:
        pick, replayed = pack_pick(session, actor.business_id, carton_id, payload.pick_id,
            actor.id, payload.scan_sku, payload.scan_carton)
    except DomainError as error:
        if error.message.startswith("Packing scan verification failed"):
            session.commit()
        raise
    session.commit()
    return {"pick_id": pick.id, "status": pick.status, "replayed": replayed}


@router.post("/outbound/cartons/{carton_id}/seal")
def outbound_seal(carton_id: int, request: Request,
                  x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    carton = seal_carton(session, actor.business_id, carton_id, actor.id)
    session.commit()
    return {"id": carton.id, "status": carton.status}


@router.get("/outbound/shipments")
def outbound_shipments(request: Request, session: Session = Depends(get_db)):
    return list_shipments(session, read_access(request, session, False))


@router.post("/outbound/orders/{order_id}/dispatch")
def outbound_dispatch(order_id: int, payload: DispatchIn, request: Request,
                      idempotency_key: str = Header(default=""),
                      x_csrf_token: str = Header(default=""), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    require_role(actor, {"owner", "manager"})
    shipment, replayed = dispatch_order(session, actor.business_id, order_id,
        actor.id, payload.carrier, payload.tracking_reference, idempotency_key)
    session.commit()
    return {"id": shipment.id, "order_id": shipment.order_id,
            "tracking_reference": shipment.tracking_reference, "replayed": replayed}


@router.get("/health")
def health():
    return {"status": "ok", "app": "elveriq"}


@router.post("/import/products")
async def import_products(request: Request, file: UploadFile = File(...),
                          x_csrf_token: str = Header(default=""),
                          session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token, owner_only=True)
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise DomainError("Upload a .csv file")
    content = await file.read(1_000_001)
    if len(content) > 1_000_000:
        raise DomainError("CSV file must be 1 MB or less")
    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None or not {"sku", "name"}.issubset(reader.fieldnames):
            raise DomainError("CSV must contain sku and name column headers")
        created = skipped = 0
        seen = set()
        for row in reader:
            if created + skipped >= 1000:
                raise DomainError("Import a maximum of 1,000 products per file")
            sku = (row.get("sku") or "").strip().upper()
            if not sku:
                raise DomainError("Every CSV row must have a SKU")
            if sku in seen or session.scalar(select(Product.id).where(
                    Product.business_id == actor.business_id, Product.sku == sku)):
                skipped += 1
                seen.add(sku)
                continue
            seen.add(sku)
            create_product(session, actor.business_id, sku, row.get("name") or "",
                           int(row.get("price_cents") or 0),
                           int(row.get("reorder_point") or 5), row.get("unit") or "each")
            created += 1
        session.commit()
        return {"created": created, "skipped": skipped}
    except (UnicodeDecodeError, ValueError, csv.Error) as exc:
        session.rollback()
        raise DomainError("Invalid CSV encoding or numeric value") from exc


def csv_cell(value):
    """Protect spreadsheet programs from formula injection on CSV opening."""
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


@router.get("/export/inventory.csv")
def export_inventory(request: Request, demo: bool = False, session: Session = Depends(get_db)):
    rows = list_inventory(session, read_access(request, session, demo))
    stream = io.StringIO()
    writer = csv.writer(stream)
    fields = ["sku", "name", "warehouse", "on_hand", "reserved", "available", "reorder_point"]
    writer.writerow(fields)
    for row in rows:
        writer.writerow([csv_cell(row[field]) for field in fields])
    return Response(stream.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="elveriq-inventory.csv"'})

class InboundNoticeItemIn(BaseModel):
    purchase_line_id: int = Field(gt=0)
    expected: int = Field(ge=1, le=1_000_000)


class InboundNoticeCreateIn(BaseModel):
    purchase_order_id: int = Field(gt=0)
    reference: str = Field(min_length=1, max_length=100)
    supplier_reference: str = Field(default="", max_length=120)
    dock: str = Field(default="", max_length=64)
    items: list[InboundNoticeItemIn] = Field(min_length=1, max_length=100)


class InboundReceiptScanIn(BaseModel):
    line_id: int = Field(gt=0)
    scan_sku: str = Field(min_length=1, max_length=80)
    accepted: int = Field(default=0, ge=0, le=1_000_000)
    damaged: int = Field(default=0, ge=0, le=1_000_000)
    damage_note: str = Field(default="", max_length=250)


class InboundNoteIn(BaseModel):
    note: str = Field(default="", max_length=250)

@router.get('/inbound/notices')
def inbound_notices(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
                    session: Session = Depends(get_db)):
    return list_notices(session, read_access(request, session, False), warehouse_id)


@router.post('/inbound/notices', status_code=201)
def inbound_create(payload: InboundNoticeCreateIn, request: Request,
                   x_csrf_token: str = Header(default=''), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    require_role(actor, {'owner','manager'})
    notice = create_notice(session, actor.business_id, payload.purchase_order_id,
        payload.reference, payload.supplier_reference, payload.dock,
        [item.model_dump() for item in payload.items], actor.id)
    session.commit()
    return {'id': notice.id, 'status': notice.status, 'reference': notice.reference}


@router.post('/inbound/notices/{notice_id}/arrive')
def inbound_arrive(notice_id: int, request: Request,
                   x_csrf_token: str = Header(default=''), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    notice, replayed = arrive_notice(session, actor.business_id, notice_id, actor.id)
    session.commit()
    return {'id': notice.id, 'status': notice.status, 'replayed': replayed}

@router.post('/inbound/notices/{notice_id}/scan')
def inbound_scan(notice_id: int, payload: InboundReceiptScanIn, request: Request,
                 idempotency_key: str = Header(default=''),
                 x_csrf_token: str = Header(default=''), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    receipt, replayed = scan_receipt(session, actor.business_id, notice_id,
        payload.line_id, payload.scan_sku, payload.accepted, payload.damaged,
        payload.damage_note, actor.id, idempotency_key)
    session.commit()
    return {'id': receipt.id, 'accepted': receipt.accepted,
            'damaged': receipt.damaged, 'replayed': replayed}


@router.post('/inbound/notices/{notice_id}/close')
def inbound_close(notice_id: int, payload: InboundNoteIn, request: Request,
                  x_csrf_token: str = Header(default=''), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    require_role(actor, {'owner','manager'})
    notice, short = close_notice(session, actor.business_id, notice_id, actor.id, payload.note)
    session.commit()
    return {'id': notice.id, 'status': notice.status, 'short': short}


@router.post('/inbound/notices/{notice_id}/cancel')
def inbound_cancel(notice_id: int, payload: InboundNoteIn, request: Request,
                   x_csrf_token: str = Header(default=''), session: Session = Depends(get_db)):
    actor = write_access(request, session, x_csrf_token)
    require_role(actor, {'owner','manager'})
    notice = cancel_notice(session, actor.business_id, notice_id, actor.id, payload.note)
    session.commit()
    return {'id': notice.id, 'status': notice.status}

@router.get('/inbound/notices/{notice_id}/receipts')
def inbound_receipts(notice_id: int, request: Request, session: Session = Depends(get_db)):
    return receipt_history(session, read_access(request, session, False), notice_id)


@router.get('/inbound/notices/{notice_id}/events')
def inbound_events(notice_id: int, request: Request, session: Session = Depends(get_db)):
    return notice_events(session, read_access(request, session, False), notice_id)

class ExceptionCreateIn(BaseModel):
    warehouse_id: int | None = Field(default=None,gt=0)
    source_type: str = Field(default='manual',max_length=32)
    source_id: int | None = Field(default=None,gt=0)
    category: str = Field(default='manual',max_length=40)
    severity: str = Field(default='medium',max_length=12)
    title: str = Field(min_length=3,max_length=160)
    detail: str = Field(default='',max_length=500)


class ExceptionAssignIn(BaseModel):
    user_id: int = Field(gt=0)


class ExceptionNoteIn(BaseModel):
    note: str = Field(min_length=1,max_length=500)

@router.get('/exceptions')
def exception_queue(request:Request,status:str|None=None,
    warehouse_id:int|None=Query(default=None,gt=0),severity:str|None=None,
    session:Session=Depends(get_db)):
    return list_cases(session,read_access(request,session,False),status,warehouse_id,severity)


@router.post('/exceptions',status_code=201)
def exception_open(payload:ExceptionCreateIn,request:Request,
    idempotency_key:str=Header(default=''),x_csrf_token:str=Header(default=''),
    session:Session=Depends(get_db)):
    actor=write_access(request,session,x_csrf_token)
    case,replayed=open_case(session,actor.business_id,payload.warehouse_id,
        payload.category,payload.severity,payload.source_type,payload.source_id,
        payload.title,payload.detail,actor.id,idempotency_key)
    session.commit()
    return {'id':case.id,'status':case.status,'replayed':replayed}

@router.post('/exceptions/{case_id}/assign')
def exception_assign(case_id:int,payload:ExceptionAssignIn,request:Request,
    x_csrf_token:str=Header(default=''),session:Session=Depends(get_db)):
    actor=write_access(request,session,x_csrf_token)
    require_role(actor,{'owner','manager'})
    case=assign_case(session,actor.business_id,case_id,actor.id,payload.user_id)
    session.commit()
    return {'id':case.id,'status':case.status,'assigned_user_id':case.assigned_user_id}


@router.post('/exceptions/{case_id}/acknowledge')
def exception_acknowledge(case_id:int,request:Request,
    x_csrf_token:str=Header(default=''),session:Session=Depends(get_db)):
    actor=write_access(request,session,x_csrf_token)
    case=acknowledge_case(session,actor.business_id,case_id,actor.id,
        actor.role in ('owner','manager'))
    session.commit()
    return {'id':case.id,'status':case.status}


@router.post('/exceptions/{case_id}/resolve')
def exception_resolve(case_id:int,payload:ExceptionNoteIn,request:Request,
    x_csrf_token:str=Header(default=''),session:Session=Depends(get_db)):
    actor=write_access(request,session,x_csrf_token)
    require_role(actor,{'owner','manager'})
    case=resolve_case(session,actor.business_id,case_id,actor.id,payload.note)
    session.commit()
    return {'id':case.id,'status':case.status}


@router.post('/exceptions/{case_id}/reopen')
def exception_reopen(case_id:int,payload:ExceptionNoteIn,request:Request,
    x_csrf_token:str=Header(default=''),session:Session=Depends(get_db)):
    actor=write_access(request,session,x_csrf_token)
    require_role(actor,{'owner','manager'})
    case=reopen_case(session,actor.business_id,case_id,actor.id,payload.note)
    session.commit()
    return {'id':case.id,'status':case.status}

@router.get('/exceptions/{case_id}/events')
def exception_events(case_id:int,request:Request,session:Session=Depends(get_db)):
    return case_history(session,read_access(request,session,False),case_id)


@router.post('/exceptions/{case_id}/notes')
def exception_note(case_id:int,payload:ExceptionNoteIn,request:Request,
    x_csrf_token:str=Header(default=''),session:Session=Depends(get_db)):
    actor=write_access(request,session,x_csrf_token)
    case=comment_case(session,actor.business_id,case_id,actor.id,payload.note)
    session.commit()
    return {'id':case.id,'status':case.status}

class ShipmentMilestoneIn(BaseModel):
    milestone: str = Field(min_length=3,max_length=24)
    location: str = Field(default='',max_length=120)
    note: str = Field(default='',max_length=250)


@router.get('/shipping/tracking')
def tracking_overview(request:Request,
    warehouse_id:int|None=Query(default=None,gt=0),session:Session=Depends(get_db)):
    return shipment_overview(session,read_access(request,session,False),warehouse_id)


@router.get('/shipping/shipments/{shipment_id}/events')
def tracking_history(shipment_id:int,request:Request,
    after_id:int|None=Query(default=None,ge=0),
    limit:int=Query(default=200,ge=1,le=200),session:Session=Depends(get_db)):
    return shipment_timeline(session,read_access(request,session,False),shipment_id,after_id,limit)


@router.post('/shipping/shipments/{shipment_id}/events',status_code=201)
def tracking_add(shipment_id:int,payload:ShipmentMilestoneIn,request:Request,
    idempotency_key:str=Header(default=''),x_csrf_token:str=Header(default=''),
    session:Session=Depends(get_db)):
    actor=write_access(request,session,x_csrf_token)
    require_role(actor,{'owner','manager'})
    row,replayed=record_milestone(session,actor.business_id,shipment_id,
        payload.milestone,payload.location,payload.note,actor.id,idempotency_key)
    session.commit()
    return {'id':row.id,'shipment_id':row.shipment_id,'milestone':row.milestone,
            'replayed':replayed,'source':'manual_operator_entry'}

@router.get('/operations/metrics')
def operations_metrics_api(request:Request,
    warehouse_id:int|None=Query(default=None,gt=0),session:Session=Depends(get_db)):
    bid=read_access(request,session,False)
    return operational_metrics(session,bid,warehouse_id)

@router.get('/outbound/orders/{order_id}/manifest.csv')
def outbound_carton_manifest(order_id:int,request:Request,session:Session=Depends(get_db)):
    from .models import OutboundCarton,OutboundCartonItem
    bid=read_access(request,session,False)
    order=_order(session,bid,order_id)
    cartons=session.scalars(select(OutboundCarton).where(
        OutboundCarton.business_id==bid,OutboundCarton.order_id==order.id)).all()
    if not cartons or any(c.status not in ('sealed','shipped') for c in cartons):
        raise DomainError('Manifest requires all cartons sealed or shipped',409)
    stream=io.StringIO()
    writer=csv.writer(stream)
    writer.writerow(['order_id','warehouse_id','carton_code','pick_id','sku','quantity','carton_status'])
    for carton in cartons:
        rows=session.execute(select(OutboundCartonItem,Product.sku).join(
            OutboundPick,OutboundPick.id==OutboundCartonItem.pick_id).join(
            Product,Product.id==OutboundPick.product_id).where(
            OutboundCartonItem.business_id==bid,OutboundCartonItem.carton_id==carton.id,
            OutboundPick.business_id==bid,Product.business_id==bid)).all()
        for item,sku in rows:
            writer.writerow([order.id,order.warehouse_id,csv_cell(carton.code),item.pick_id,
                csv_cell(sku),item.quantity,csv_cell(carton.status)])
    return Response(stream.getvalue(),media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition':f'attachment; filename="elveriq-manifest-{order.id}.csv"'})

from . import warehouse_reports

@router.get('/reports/inventory-health')
def report_inventory_health(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
        session: Session = Depends(get_db)):
    bid = read_access(request, session, False)
    return warehouse_reports.inventory_health(session, bid, warehouse_id)

@router.get('/reports/bin-capacity')
def report_bin_capacity(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
        session: Session = Depends(get_db)):
    bid = read_access(request, session, False)
    return warehouse_reports.bin_capacity(session, bid, warehouse_id)

@router.get('/reports/receiving-quality')
def report_receiving_quality(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
        session: Session = Depends(get_db)):
    bid = read_access(request, session, False)
    return warehouse_reports.receiving_quality(session, bid, warehouse_id)

@router.get('/reports/purchase-backlog')
def report_purchase_backlog(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
        session: Session = Depends(get_db)):
    bid = read_access(request, session, False)
    return warehouse_reports.purchase_backlog(session, bid, warehouse_id)

@router.get('/reports/picking-pipeline')
def report_picking_pipeline(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
        session: Session = Depends(get_db)):
    bid = read_access(request, session, False)
    return warehouse_reports.picking_pipeline(session, bid, warehouse_id)

@router.get('/reports/packing-pipeline')
def report_packing_pipeline(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
        session: Session = Depends(get_db)):
    bid = read_access(request, session, False)
    return warehouse_reports.packing_pipeline(session, bid, warehouse_id)

@router.get('/reports/dispatch-activity')
def report_dispatch_activity(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
        session: Session = Depends(get_db)):
    bid = read_access(request, session, False)
    return warehouse_reports.dispatch_activity(session, bid, warehouse_id)

@router.get('/reports/delivery-visibility')
def report_delivery_visibility(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
        session: Session = Depends(get_db)):
    bid = read_access(request, session, False)
    return warehouse_reports.delivery_visibility(session, bid, warehouse_id)

@router.get('/reports/incident-risk')
def report_incident_risk(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
        session: Session = Depends(get_db)):
    bid = read_access(request, session, False)
    return warehouse_reports.incident_risk(session, bid, warehouse_id)

@router.get('/reports/workforce-load')
def report_workforce_load(request: Request, warehouse_id: int | None = Query(default=None, gt=0),
        session: Session = Depends(get_db)):
    bid = read_access(request, session, False)
    return warehouse_reports.workforce_load(session, bid, warehouse_id)


from .integrity_audit import audit as warehouse_integrity_audit

@router.get('/reports/integrity-audit')
def report_integrity_audit(request: Request,
        warehouse_id: int | None = Query(default=None, gt=0),
        severity: str | None = Query(default=None, pattern='^(critical|warning)$'),
        rule: str | None = Query(default=None, min_length=1, max_length=64),
        session: Session = Depends(get_db)):
    """Read-only, scoped safety findings; no physical reconciliation claims."""
    bid = read_access(request, session, False)
    return warehouse_integrity_audit(session, bid, warehouse_id, severity=severity, rule=rule)

@router.get('/reports/integrity-audit.csv')
def export_integrity_audit(request: Request,
        warehouse_id: int | None = Query(default=None, gt=0),
        severity: str | None = Query(default=None, pattern='^(critical|warning)$'),
        rule: str | None = Query(default=None, min_length=1, max_length=64),
        session: Session = Depends(get_db)):
    """Export the same read-only, tenant-scoped findings as the JSON endpoint."""
    bid = read_access(request, session, False)
    report = warehouse_integrity_audit(session, bid, warehouse_id, severity=severity, rule=rule)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(['rule', 'severity', 'affected_records', 'sample_ids', 'samples_truncated', 'description'])
    for entry in report['checks']:
        writer.writerow([csv_cell(entry['rule']), csv_cell(entry['severity']),
                         entry['affected_records'],
                         csv_cell(' '.join(str(n) for n in entry['sample_ids'])),
                         entry['samples_truncated'], csv_cell(entry['description'])])
    return Response(stream.getvalue(), media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="elveriq-integrity-audit.csv"',
                 'Cache-Control': 'no-store'})
