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
