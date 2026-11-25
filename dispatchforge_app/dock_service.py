"""Tenant-safe, explicitly manual dock and vehicle appointment scheduling.

This ledger never receives inventory, books a carrier, or generates ASN goods issue.
On PostgreSQL each overlapping decision locks the shared warehouse row.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .errors import DomainError
from .models import (DockDoor, DockAppointment, DockAppointmentEvent, Warehouse, utcnow)

ACTIVE = {'scheduled', 'checked_in'}

def _warehouse(session: Session, bid: int, wid: int, lock=False):
    q = select(Warehouse).where(Warehouse.id == wid, Warehouse.business_id == bid)
    if lock:
        q = q.with_for_update()
    warehouse = session.scalar(q)
    if warehouse is None:
        raise DomainError('Warehouse not found', 404)
    return warehouse

def _door(session: Session, bid: int, door_id: int):
    door = session.scalar(select(DockDoor).where(DockDoor.id == door_id, DockDoor.business_id == bid))
    if door is None:
        raise DomainError('Dock door not found', 404)
    return door

def _appointment(session: Session, bid: int, appointment_id: int):
    appt = session.scalar(select(DockAppointment).where(
        DockAppointment.id == appointment_id, DockAppointment.business_id == bid))
    if appt is None:
        raise DomainError('Dock appointment not found', 404)
    return appt

def _event(session, bid, appt, action, actor_id, note=''):
    session.add(DockAppointmentEvent(business_id=bid, appointment_id=appt.id,
                                    action=action, actor_id=actor_id, note=note))

def _clean(value, label, maximum):
    value = (value or '').strip()
    if not value or len(value) > maximum:
        raise DomainError(f'{label} must be 1 to {maximum} characters')
    return value

def _serialize(appointment):
    return {'id': appointment.id, 'warehouse_id': appointment.warehouse_id,
       'door_id': appointment.door_id, 'direction': appointment.direction,
       'reference': appointment.reference, 'carrier': appointment.carrier,
       'vehicle_plate': appointment.vehicle_plate, 'note': appointment.note,
       'start_at': appointment.start_at.isoformat() + 'Z',
       'end_at': appointment.end_at.isoformat() + 'Z', 'status': appointment.status,
       'checked_in_at': appointment.checked_in_at.isoformat() + 'Z' if appointment.checked_in_at else None,
       'completed_at': appointment.completed_at.isoformat() + 'Z' if appointment.completed_at else None}


def create_door(session, bid, wid, code, purpose):
    _warehouse(session, bid, wid)
    code = _clean(code, 'Door code', 64).upper()
    if purpose not in {'inbound', 'outbound', 'both'}:
        raise DomainError('Door purpose must be inbound, outbound or both')
    if session.scalar(select(DockDoor.id).where(DockDoor.business_id == bid,
         DockDoor.warehouse_id == wid, DockDoor.code == code)):
        raise DomainError('Door code already exists in this warehouse', 409)
    door = DockDoor(business_id=bid, warehouse_id=wid, code=code, purpose=purpose)
    session.add(door); session.flush()
    return {'id': door.id, 'warehouse_id': wid, 'code': code, 'purpose': purpose, 'active': True}


def list_doors(session, bid, wid=None):
    if wid is not None: _warehouse(session, bid, wid)
    q = select(DockDoor).where(DockDoor.business_id == bid)
    if wid is not None: q = q.where(DockDoor.warehouse_id == wid)
    return [{'id': d.id, 'warehouse_id': d.warehouse_id, 'code': d.code,
             'purpose': d.purpose, 'active': d.active} for d in session.scalars(q.order_by(DockDoor.id))]


def _utc_time(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError('timezone required')
        return result.astimezone(timezone.utc).replace(tzinfo=None)
    except (AttributeError, TypeError, ValueError):
        raise DomainError('Use an ISO 8601 timestamp with UTC offset')

def _window(start, end):
    start, end = _utc_time(start), _utc_time(end)
    if end - start < timedelta(minutes=15) or end - start > timedelta(hours=24):
        raise DomainError('Appointment must last 15 minutes to 24 hours')
    if start < datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1):
        raise DomainError('Cannot schedule a window more than one day in the past')
    return start, end


def schedule(session, bid, wid, door_id, direction, reference, start_at, end_at,
             actor_id, key, carrier='', vehicle_plate='', note=''):
    if direction not in {'inbound','outbound'}:
        raise DomainError('Direction must be inbound or outbound')
    reference = _clean(reference, 'Reference', 100)
    carrier = (carrier or '').strip()
    plate = (vehicle_plate or '').strip()
    note = (note or '').strip()
    if len(carrier) > 120 or len(plate) > 64 or len(note) > 300:
        raise DomainError('Appointment details are too long')
    start, end = _window(start_at, end_at)
    key = _clean(key, 'Idempotency-Key', 128)
    if len(key) < 8: raise DomainError('Idempotency-Key must have at least 8 characters')
    content = [wid, door_id, direction, reference, start.isoformat(), end.isoformat(), carrier, plate, note]
    fingerprint = hashlib.sha256(json.dumps(content).encode()).hexdigest()
    existing = session.scalar(select(DockAppointment).where(
        DockAppointment.business_id == bid, DockAppointment.request_key == key))
    if existing:
        if existing.fingerprint != fingerprint: raise DomainError('Idempotency key was reused with different appointment details', 409)
        return _serialize(existing), True
    _warehouse(session, bid, wid, lock=True)
    door = _door(session, bid, door_id)
    if door.warehouse_id != wid or not door.active:
        raise DomainError('Dock door is unavailable in this warehouse', 409)
    if door.purpose not in {'both', direction}:
        raise DomainError('Dock door does not serve this direction', 409)
    # Cross-request lock of the warehouse serializes overlapping inserts in PostgreSQL.
    overlapping = session.scalar(select(DockAppointment.id).where(
        DockAppointment.business_id == bid, DockAppointment.door_id == door_id,
        DockAppointment.status.in_(ACTIVE),
        DockAppointment.start_at < end, DockAppointment.end_at > start))
    if overlapping is not None: raise DomainError('Dock door is already reserved for that window', 409)
    appt = DockAppointment(business_id=bid, warehouse_id=wid, door_id=door_id,
        direction=direction, reference=reference, carrier=carrier, vehicle_plate=plate,
        note=note, start_at=start, end_at=end, request_key=key,
        fingerprint=fingerprint, created_by=actor_id, status='scheduled')
    session.add(appt); session.flush()
    _event(session, bid, appt, 'scheduled', actor_id, note)
    return _serialize(appt), False


def availability(session, bid, door_id, start_at, end_at):
    door = _door(session, bid, door_id)
    _warehouse(session, bid, door.warehouse_id)
    start, end = _window(start_at, end_at)
    matches = session.scalars(select(DockAppointment).where(
        DockAppointment.business_id == bid, DockAppointment.door_id == door.id,
        DockAppointment.status.in_(ACTIVE), DockAppointment.start_at < end,
        DockAppointment.end_at > start).order_by(DockAppointment.start_at)).all()
    return {'door_id': door.id, 'available': door.active and len(matches) == 0,
            'conflicts': [{'id': a.id, 'reference': a.reference,
                'start_at': a.start_at.isoformat() + 'Z',
                'end_at': a.end_at.isoformat() + 'Z'} for a in matches]}


def list_appointments(session, bid, wid=None, status=None, before_id=None, limit=100):
    if wid is not None: _warehouse(session, bid, wid)
    if status is not None and status not in {'scheduled','checked_in','completed','canceled','no_show'}:
        raise DomainError('Invalid appointment status')
    q = select(DockAppointment).where(DockAppointment.business_id == bid)
    if wid is not None: q = q.where(DockAppointment.warehouse_id == wid)
    if status: q = q.where(DockAppointment.status == status)
    if before_id: q = q.where(DockAppointment.id < before_id)
    return [_serialize(a) for a in session.scalars(q.order_by(DockAppointment.id.desc()).limit(limit))]
