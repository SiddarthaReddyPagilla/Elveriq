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

def inventory_health(session, bid, wid=None):
    base = _scope(session, bid, wid)
    q = select(StockLevel.on_hand, StockLevel.reserved, Product.reorder_point).join(
        Product, (Product.id == StockLevel.product_id) & (Product.business_id == bid))
    rows = session.execute(_where(q, StockLevel, bid, wid)).all()
    on_hand = sum(int(r[0]) for r in rows)
    reserved = sum(int(r[1]) for r in rows)
    return {**base, 'sku_locations': len(rows), 'on_hand_units': on_hand,
        'reserved_units': reserved, 'available_units': on_hand - reserved,
        'below_reorder_point': sum(r[0] < r[2] for r in rows),
        'fully_reserved_locations': sum(r[0] > 0 and r[1] == r[0] for r in rows)}

def bin_capacity(session, bid, wid=None):
    base = _scope(session, bid, wid)
    bins = session.execute(_where(select(WarehouseBin.id, WarehouseBin.capacity_units,
        WarehouseBin.active), WarehouseBin, bid, wid)).all()
    stock = session.execute(_where(select(BinStock.bin_id, BinStock.on_hand,
        BinStock.allocated), BinStock, bid, wid)).all()
    occupancy = {}
    for bin_id, units, allocated in stock:
        stored, reserved = occupancy.get(bin_id, (0, 0))
        occupancy[bin_id] = (stored + units, reserved + allocated)
    capacity = sum(c for _, c, active in bins if active and c is not None)
    stored = sum(units for _, units, _ in stock)
    return {**base, 'bins': len(bins), 'active_bins': sum(bool(b[2]) for b in bins),
        'capacity_defined_bins': sum(b[1] is not None for b in bins),
        'configured_active_capacity': capacity, 'placed_units': stored,
        'allocated_placed_units': sum(a for _, _, a in stock),
        'occupied_bins': sum(occupancy.get(b[0], (0, 0))[0] > 0 for b in bins),
        'over_capacity_bins': sum(bool(active and cap is not None and
            occupancy.get(bin_id, (0, 0))[0] > cap) for bin_id, cap, active in bins)}

def receiving_quality(session, bid, wid=None):
    base = _scope(session, bid, wid)
    q = (select(func.coalesce(func.sum(InboundNoticeLine.expected), 0),
        func.coalesce(func.sum(InboundNoticeLine.accepted), 0),
        func.coalesce(func.sum(InboundNoticeLine.damaged), 0))
        .join(InboundNotice, InboundNotice.id == InboundNoticeLine.notice_id)
        .where(InboundNotice.business_id == bid, InboundNoticeLine.business_id == bid,
            InboundNotice.status != 'canceled'))
    if wid is not None: q = q.where(InboundNotice.warehouse_id == wid)
    expected, accepted, damaged = session.execute(q).one()
    return {**base, 'planned_notices': _count(session, InboundNotice, bid, wid,
        InboundNotice.status == 'planned'), 'arrived_notices': _count(session,
        InboundNotice, bid, wid, InboundNotice.status == 'arrived'),
        'closed_notices': _count(session, InboundNotice, bid, wid,
        InboundNotice.status == 'closed'), 'expected_units': int(expected),
        'accepted_units': int(accepted), 'damaged_units': int(damaged),
        'unaccounted_units': max(0, int(expected) - int(accepted) - int(damaged))}

def purchase_backlog(session, bid, wid=None):
    base = _scope(session, bid, wid)
    q = (select(func.coalesce(func.sum(PurchaseOrderLine.ordered_quantity), 0),
        func.coalesce(func.sum(PurchaseOrderLine.received_quantity), 0))
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
        .where(PurchaseOrder.business_id == bid, PurchaseOrderLine.business_id == bid,
            PurchaseOrder.status != 'canceled'))
    if wid is not None: q = q.where(PurchaseOrder.warehouse_id == wid)
    ordered, received = session.execute(q).one()
    return {**base, 'open_purchase_orders': _count(session, PurchaseOrder, bid, wid,
        PurchaseOrder.status.in_(('ordered', 'partial'))),
        'ordered_units': int(ordered), 'received_units': int(received),
        'outstanding_units': max(0, int(ordered) - int(received))}

def picking_pipeline(session, bid, wid=None):
    base = _scope(session, bid, wid)
    states = ('queued', 'assigned', 'in_progress', 'picked', 'packed', 'shipped', 'canceled')
    q = _where(select(OutboundPick.status, func.count(OutboundPick.id),
        func.coalesce(func.sum(OutboundPick.quantity), 0)).group_by(
        OutboundPick.status), OutboundPick, bid, wid)
    results = {state: {'picks': 0, 'units': 0} for state in states}
    for status, count, units in session.execute(q):
        if status in results: results[status] = {'picks': int(count), 'units': int(units)}
    return {**base, 'by_status': results, 'staged_units': sum(results[s]['units']
        for s in ('picked', 'packed')), 'open_picks': sum(results[s]['picks']
        for s in ('queued', 'assigned', 'in_progress'))}
