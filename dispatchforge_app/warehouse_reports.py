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

def packing_pipeline(session, bid, wid=None):
    base = _scope(session, bid, wid)
    states = ('open', 'sealed', 'shipped')
    q = _where(select(OutboundCarton.status, func.count(OutboundCarton.id))
        .group_by(OutboundCarton.status), OutboundCarton, bid, wid)
    counts = dict.fromkeys(states, 0)
    counts.update({status: int(count) for status, count in session.execute(q) if status in counts})
    item_q = (select(func.count(OutboundCartonItem.id),
        func.coalesce(func.sum(OutboundCartonItem.quantity), 0))
        .join(OutboundCarton, OutboundCarton.id == OutboundCartonItem.carton_id)
        .where(OutboundCarton.business_id == bid, OutboundCartonItem.business_id == bid))
    if wid is not None: item_q = item_q.where(OutboundCarton.warehouse_id == wid)
    items, units = session.execute(item_q).one()
    return {**base, 'by_status': counts, 'packed_lines': int(items),
        'packed_units': int(units), 'awaiting_seal': counts['open']}

def dispatch_activity(session, bid, wid=None):
    base = _scope(session, bid, wid)
    now = utcnow()
    q = _where(select(OutboundShipment.carrier, func.count(OutboundShipment.id))
        .group_by(OutboundShipment.carrier).order_by(func.count(OutboundShipment.id).desc(),
        OutboundShipment.carrier).limit(20), OutboundShipment, bid, wid)
    return {**base, 'shipments': _count(session, OutboundShipment, bid, wid),
        'shipped_last_7_days': _count(session, OutboundShipment, bid, wid,
            OutboundShipment.shipped_at >= now - timedelta(days=7)),
        'top_carriers': [{'carrier': name, 'shipments': int(count)}
            for name, count in session.execute(q)]}

def delivery_visibility(session, bid, wid=None):
    base = _scope(session, bid, wid)
    q = _where(select(OutboundShipment.id), OutboundShipment, bid, wid)
    ship_ids = q.subquery()
    latest = (select(ShipmentTrackingUpdate.shipment_id.label('shipment_id'),
        func.max(ShipmentTrackingUpdate.id).label('latest_id')).where(
        ShipmentTrackingUpdate.business_id == bid,
        ShipmentTrackingUpdate.shipment_id.in_(select(ship_ids.c.id)))
        .group_by(ShipmentTrackingUpdate.shipment_id).subquery())
    counts = session.execute(select(ShipmentTrackingUpdate.milestone,
        func.count(ShipmentTrackingUpdate.id)).join(
        latest, ShipmentTrackingUpdate.id == latest.c.latest_id)
        .where(ShipmentTrackingUpdate.business_id == bid).group_by(
        ShipmentTrackingUpdate.milestone)).all()
    total = _count(session, OutboundShipment, bid, wid)
    manual = sum(int(n) for _, n in counts)
    return {**base, 'total_shipments': total,
        'no_milestone_recorded': total - manual,
        'latest_manual_milestones': {state: int(n) for state, n in counts},
        'carrier_verified': False}

def incident_risk(session, bid, wid=None):
    base = _scope(session, bid, wid)
    active = WarehouseException.status != 'resolved'
    q = _where(select(WarehouseException.severity, func.count(WarehouseException.id))
        .where(active).group_by(WarehouseException.severity), WarehouseException, bid, wid)
    severities = {name: 0 for name in ('low', 'medium', 'high', 'critical')}
    severities.update({name: int(n) for name, n in session.execute(q)})
    return {**base, 'active_by_severity': severities,
        'open_total': sum(severities.values()),
        'unassigned_open': _count(session, WarehouseException, bid, wid, active,
            WarehouseException.assigned_user_id.is_(None)),
        'overdue_open': _count(session, WarehouseException, bid, wid, active,
            WarehouseException.due_at < utcnow())}

def workforce_load(session, bid, wid=None):
    base = _scope(session, bid, wid)
    active = WarehouseTask.status.in_(('queued', 'assigned', 'in_progress'))
    q = _where(select(WarehouseTask.assigned_user_id, func.count(WarehouseTask.id),
        func.coalesce(func.sum(WarehouseTask.quantity), 0)).where(active)
        .group_by(WarehouseTask.assigned_user_id).order_by(
        func.count(WarehouseTask.id).desc(), WarehouseTask.assigned_user_id)
        .limit(100), WarehouseTask, bid, wid)
    results = [{'user_id': user, 'tasks': int(count), 'units': int(units)}
        for user, count, units in session.execute(q)]
    return {**base, 'active_tasks': _count(session, WarehouseTask, bid, wid, active),
        'unassigned_tasks': _count(session, WarehouseTask, bid, wid, active,
            WarehouseTask.assigned_user_id.is_(None)),
        'worker_load': results, 'worker_load_limit': 100}
