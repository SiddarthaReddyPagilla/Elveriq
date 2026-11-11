"""JSON API for the warehouse SaaS demo and authenticated workspaces."""
from datetime import date
import csv
import io
from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .auth import actor_from_session, check_csrf, require_role
from .demo import DEMO_SLUG
from .errors import DomainError
from .inventory_service import (apply_stock_delta, create_product, create_supplier,
                                create_warehouse, list_inventory, list_movements)
from .models import Business, CustomerOrder, Product, Supplier, Warehouse
from .order_service import create_order, change_order_status, list_orders

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


class OrderItemIn(BaseModel):
    sku: str
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


@router.get("/health")
def health():
    return {"status": "ok", "app": "dispatchforge"}
