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
