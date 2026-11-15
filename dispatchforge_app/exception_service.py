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

def open_case(session:Session,bid:int,warehouse_id:int|None,category:str,severity:str,
              source_type:str,source_id:int|None,title:str,detail:str,actor_id:int,key:str):
    """Incident creation is transaction-local and deduplicated per tenant."""
    title=(title or '').strip()
    detail=(detail or '').strip()
    if category not in CATEGORIES or severity not in SLA_HOURS:
        raise DomainError('Unknown exception category or severity')
    if not (3<=len(title)<=160) or len(detail)>500:
        raise DomainError('Exception title must be 3–160 characters; details at most 500')
    if not isinstance(key,str) or not KEY.fullmatch(key):
        raise DomainError('Idempotency-Key required (8–128 safe characters)')
    actual_warehouse=_source_warehouse(session,bid,source_type,source_id,warehouse_id)
    details=dict(warehouse_id=actual_warehouse,category=category,severity=severity,
        source_type=source_type,source_id=source_id,title=title,detail=detail)
    fp=_fingerprint(details)
    prev=session.scalar(select(WarehouseException).where(
        WarehouseException.business_id==bid,WarehouseException.dedupe_key==key))
    if prev:
        if prev.request_fingerprint!=fp:
            raise DomainError('Exception key already used with different details',409)
        return prev,True
    inserted=session.scalar((pg_insert(WarehouseException) if session.get_bind().dialect.name=='postgresql'
        else sqlite_insert(WarehouseException)).values(
        business_id=bid,warehouse_id=actual_warehouse,category=category,severity=severity,
        source_type=source_type,source_id=source_id,title=title,detail=detail,
        status='open',dedupe_key=key,request_fingerprint=fp,created_by=actor_id,
        due_at=utcnow()+timedelta(hours=SLA_HOURS[severity]),created_at=utcnow()
    ).on_conflict_do_nothing(index_elements=['business_id','dedupe_key']).returning(WarehouseException.id))
    if inserted is None:
        prev=session.scalar(select(WarehouseException).where(
            WarehouseException.business_id==bid,WarehouseException.dedupe_key==key))
        if prev is None or prev.request_fingerprint!=fp:
            raise DomainError('Exception key conflict',409)
        return prev,True
    case=session.get(WarehouseException,inserted)
    _event(session,case,actor_id,'opened',f'{category}/{severity}')
    session.flush()
    return case,False

def list_cases(session:Session,bid:int,status:str|None=None,warehouse_id:int|None=None,
               severity:str|None=None):
    q=select(WarehouseException).where(WarehouseException.business_id==bid)
    if status:
        if status not in {'open','acknowledged','resolved'}:raise DomainError('Invalid case status')
        q=q.where(WarehouseException.status==status)
    if severity:
        if severity not in SLA_HOURS:raise DomainError('Invalid severity')
        q=q.where(WarehouseException.severity==severity)
    if warehouse_id is not None:q=q.where(WarehouseException.warehouse_id==warehouse_id)
    now=utcnow()
    output=[]
    for case in session.scalars(q.order_by(WarehouseException.id.desc()).limit(200)):
        due=case.due_at
        # SQLite returns naive UTC datetimes even when timezone=True.
        if due.tzinfo is None:due=due.replace(tzinfo=now.tzinfo)
        output.append({'id':case.id,'warehouse_id':case.warehouse_id,
            'source_type':case.source_type,'source_id':case.source_id,
            'category':case.category,'severity':case.severity,
            'title':case.title,'detail':case.detail,'status':case.status,
            'assigned_user_id':case.assigned_user_id,'created_by':case.created_by,
            'due_at':case.due_at.isoformat(),'overdue':case.status!='resolved' and due<now,
            'created_at':case.created_at.isoformat(),
            'resolved_at':case.resolved_at.isoformat() if case.resolved_at else None})
    return output

def assign_case(session:Session,bid:int,case_id:int,actor_id:int,assignee_id:int):
    case=_case(session,bid,case_id,lock=True)
    if case.status=='resolved':raise DomainError('Resolved case cannot be reassigned',409)
    worker=session.scalar(select(User).where(User.id==assignee_id,User.business_id==bid,
        User.role.in_(('owner','manager','staff'))))
    if worker is None:raise DomainError('Active assignee not found in this workspace',404)
    case.assigned_user_id=worker.id
    _event(session,case,actor_id,'assigned',f'User #{worker.id}')
    session.flush()
    return case
