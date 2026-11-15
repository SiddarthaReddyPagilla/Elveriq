"""Operational case management: explicit source checking, SLA and audited resolution."""
import hashlib
import json
from datetime import timedelta
from sqlalchemy import select,func,update
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from .errors import DomainError
from .models import (WarehouseException,WarehouseExceptionEvent,Warehouse,User,
    InboundNotice,OutboundPick,OutboundShipment,utcnow)
from .warehouse_execution import KEY

SLA_HOURS={'critical':2,'high':8,'medium':24,'low':72}
CATEGORIES={'manual','inbound_damage','inbound_shortage','outbound_short_pick','shipment_issue','stock_discrepancy'}

def _case(session:Session,bid:int,case_id:int,lock=False):
    q=select(WarehouseException).where(WarehouseException.id==case_id,WarehouseException.business_id==bid)
    result=session.scalar(q.with_for_update() if lock else q)
    if result is None:raise DomainError('Operational exception not found',404)
    return result

def _event(session,case,actor_id,action,note=''):
    session.add(WarehouseExceptionEvent(business_id=case.business_id,exception_id=case.id,
        actor_id=actor_id,action=action,note=note[:500]))

def _fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def _source_warehouse(session,bid,source_type,source_id,warehouse_id):
    if source_type=='manual':
        if source_id is not None:raise DomainError('Manual cases cannot reference foreign source IDs')
        w=session.scalar(select(Warehouse).where(Warehouse.id==warehouse_id,Warehouse.business_id==bid))
        if w is None:raise DomainError('Warehouse not found',404)
        return w.id
    lookup={'inbound_notice':(InboundNotice, 'Inbound notice'),
        'outbound_pick':(OutboundPick,'Outbound pick'),
        'shipment':(OutboundShipment,'Shipment')}
    if source_type not in lookup or not isinstance(source_id,int) or source_id<1:
        raise DomainError('Unknown operational case source',400)
    model,_=lookup[source_type]
    record=session.scalar(select(model).where(model.business_id==bid,model.id==source_id))
    if record is None:raise DomainError('Operational case source not found',404)
    if warehouse_id is not None and warehouse_id!=record.warehouse_id:
        raise DomainError('Exception source belongs to a different warehouse',409)
    return record.warehouse_id
