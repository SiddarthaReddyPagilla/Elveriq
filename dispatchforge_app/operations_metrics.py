"""Tenant-filtered current warehouse metrics; only database-backed quantities."""
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from .models import (WarehouseException,InboundNotice,OutboundPick,OutboundShipment,
    StockLevel,WarehouseTask,ShipmentTrackingUpdate)
from .models import utcnow

def operational_metrics(session:Session,bid:int,warehouse_id:int|None=None):
    def metric(model,condition=None,quantity=None):
        q=select(func.coalesce(func.sum(quantity),0)) if quantity is not None else select(func.count(model.id))
        q=q.select_from(model).where(model.business_id==bid)
        if warehouse_id is not None:q=q.where(model.warehouse_id==warehouse_id)
        if condition is not None:q=q.where(condition)
        return session.scalar(q) or 0
    open_cases=metric(WarehouseException,WarehouseException.status!='resolved')
    overdue_query=select(func.count(WarehouseException.id)).where(
        WarehouseException.business_id==bid,WarehouseException.status!='resolved',
        WarehouseException.due_at<utcnow())
    if warehouse_id is not None:overdue_query=overdue_query.where(WarehouseException.warehouse_id==warehouse_id)
    return {'warehouse_id':warehouse_id,'open_exceptions':open_cases,
        'overdue_exceptions':session.scalar(overdue_query) or 0,
        'arrived_asns':metric(InboundNotice,InboundNotice.status=='arrived'),
        'queued_picks':metric(OutboundPick,OutboundPick.status=='queued'),
        'picked_staged_units':metric(OutboundPick,OutboundPick.status.in_(('picked','packed')),OutboundPick.quantity),
        'queued_warehouse_tasks':metric(WarehouseTask,WarehouseTask.status=='queued'),
        'shipped_orders':metric(OutboundShipment),
        'warehouse_on_hand_units':metric(StockLevel,quantity=StockLevel.on_hand),
        'warehouse_reserved_units':metric(StockLevel,quantity=StockLevel.reserved),
        'source':'live_database_snapshot'}
