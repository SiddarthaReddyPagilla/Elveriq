"""Read-only, tenant-scoped operational intelligence for real warehouse ledgers.

All figures are live snapshots, not promised carrier telemetry or historical trends.
No migrations or background workers are required.
"""
from datetime import timedelta
from sqlalchemy import select, func, case, distinct
from sqlalchemy.orm import Session
from .errors import DomainError
from .models import (Warehouse, Product, StockLevel, WarehouseBin, BinStock,
    InboundNotice, InboundNoticeLine, PurchaseOrder, PurchaseOrderLine,
    OutboundPick, OutboundCarton, OutboundCartonItem, OutboundShipment,
    ShipmentTrackingUpdate, WarehouseException, WarehouseTask, utcnow)


def _scope(session: Session, bid: int, wid: int | None):
    if wid is not None and session.scalar(select(Warehouse.id).where(
            Warehouse.id == wid, Warehouse.business_id == bid)) is None:
        raise DomainError('Warehouse not found', 404)
    return {'warehouse_id': wid, 'source': 'live_database_snapshot'}


def _where(query, model, bid, wid):
    query = query.where(model.business_id == bid)
    if wid is not None:
        query = query.where(model.warehouse_id == wid)
    return query


def _count(session, model, bid, wid, *conditions):
    return int(session.scalar(_where(select(func.count(model.id)), model, bid, wid).where(*conditions)) or 0)


def _sum(session, model, bid, wid, field, *conditions):
    return int(session.scalar(_where(select(func.coalesce(func.sum(field), 0)), model, bid, wid).where(*conditions)) or 0)
