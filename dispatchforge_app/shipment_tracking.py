"""Internal manual shipment milestones. Not carrier-integrated tracking."""
import hashlib
import json
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from .models import OutboundShipment,ShipmentTrackingUpdate,utcnow
from .errors import DomainError
from .warehouse_execution import KEY

MILESTONES={'in_transit','out_for_delivery','delayed','exception','delivered'}

def _shipment(session:Session,bid:int,shipment_id:int):
    s=session.scalar(select(OutboundShipment).where(OutboundShipment.id==shipment_id,
        OutboundShipment.business_id==bid).with_for_update())
    if s is None:raise DomainError('Shipment not found',404)
    return s

def record_milestone(session:Session,bid:int,shipment_id:int,milestone:str,
    location:str,note:str,actor_id:int,key:str):
    if not isinstance(key,str) or not KEY.fullmatch(key):
        raise DomainError('Idempotency-Key required (8–128 safe characters)')
    location=(location or '').strip()
    note=(note or '').strip()
    if milestone not in MILESTONES or len(location)>120 or len(note)>250:
        raise DomainError('Invalid shipment milestone, location or note')
    if milestone in ('exception','delayed') and len(note)<3:
        raise DomainError('Delayed/exception milestones require an explanation')
    fields=dict(shipment_id=shipment_id,milestone=milestone,location=location,note=note)
    fp=hashlib.sha256(json.dumps(fields,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    prev=session.scalar(select(ShipmentTrackingUpdate).where(
        ShipmentTrackingUpdate.business_id==bid,ShipmentTrackingUpdate.idempotency_key==key))
    if prev:
        if prev.request_fingerprint!=fp:raise DomainError('Tracking key reused with different milestone',409)
        return prev,True
    shipment=_shipment(session,bid,shipment_id)
    previous=session.scalar(select(ShipmentTrackingUpdate).where(
        ShipmentTrackingUpdate.business_id==bid,ShipmentTrackingUpdate.shipment_id==shipment.id)
        .order_by(ShipmentTrackingUpdate.id.desc()).limit(1))
    if previous and previous.milestone=='delivered':
        raise DomainError('Delivered shipment cannot receive further milestones',409)
    if milestone=='in_transit' and previous and previous.milestone=='out_for_delivery':
        raise DomainError('Shipment cannot return to in-transit after out-for-delivery',409)
    inserted=session.scalar((pg_insert(ShipmentTrackingUpdate) if session.get_bind().dialect.name=='postgresql'
        else sqlite_insert(ShipmentTrackingUpdate)).values(
        business_id=bid,shipment_id=shipment.id,milestone=milestone,location=location,
        note=note,recorded_by=actor_id,idempotency_key=key,request_fingerprint=fp,
        created_at=utcnow()
    ).on_conflict_do_nothing(index_elements=['business_id','idempotency_key'])
        .returning(ShipmentTrackingUpdate.id))
    if inserted is None:
        prev=session.scalar(select(ShipmentTrackingUpdate).where(
            ShipmentTrackingUpdate.business_id==bid,ShipmentTrackingUpdate.idempotency_key==key))
        if prev is None or prev.request_fingerprint!=fp:
            raise DomainError('Tracking retry key conflict',409)
        return prev,True
    session.flush()
    return session.get(ShipmentTrackingUpdate,inserted),False

def shipment_timeline(session:Session,bid:int,shipment_id:int):
    _shipment(session,bid,shipment_id)
    records=session.scalars(select(ShipmentTrackingUpdate).where(
        ShipmentTrackingUpdate.business_id==bid,
        ShipmentTrackingUpdate.shipment_id==shipment_id).order_by(ShipmentTrackingUpdate.id)).all()
    return [{'id':e.id,'milestone':e.milestone,'location':e.location,
        'note':e.note,'recorded_by':e.recorded_by,'created_at':e.created_at.isoformat(),
        'source':'manual_operator_entry'} for e in records]


def shipment_overview(session:Session,bid:int,warehouse_id:int|None=None):
    """List at most 200 tenant-owned shipments, optionally by warehouse."""
    query=select(OutboundShipment).where(OutboundShipment.business_id==bid)
    if warehouse_id is not None:
        query=query.where(OutboundShipment.warehouse_id==warehouse_id)
    rows=session.scalars(query.order_by(OutboundShipment.id.desc()).limit(200)).all()
    # Load milestones in one query instead of an additional query per shipment.
    # The listing is capped at 200 shipments, so the IN predicate is bounded.
    shipment_ids=[ship.id for ship in rows]
    latest_by_shipment={}
    if shipment_ids:
        events=session.scalars(select(ShipmentTrackingUpdate).where(
            ShipmentTrackingUpdate.business_id==bid,
            ShipmentTrackingUpdate.shipment_id.in_(shipment_ids))
            .order_by(ShipmentTrackingUpdate.shipment_id, ShipmentTrackingUpdate.id.desc())).all()
        for event in events:
            latest_by_shipment.setdefault(event.shipment_id,event)
    result=[]
    for ship in rows:
        latest=latest_by_shipment.get(ship.id)
        result.append({'shipment_id':ship.id,'order_id':ship.order_id,'carrier':ship.carrier,
            'tracking_reference':ship.tracking_reference,
            'milestone':latest.milestone if latest else 'dispatched',
            'latest_at':(latest.created_at if latest else ship.shipped_at).isoformat(),
            'verified_by_carrier':False})
    return result
