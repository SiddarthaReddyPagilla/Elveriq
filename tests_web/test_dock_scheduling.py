"""User-facing dock appointment contracts, permissions and inventory isolation."""
from datetime import datetime, timedelta, timezone
import re
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from dispatchforge_app.models import DockAppointment, DockAppointmentEvent, StockLevel, User
from tests_web.test_warehouse_web import register


@pytest.fixture
def client(tmp_path):
    url=f"sqlite:///{tmp_path/'docks.sqlite3'}"
    db=Database(url)
    with TestClient(create_app(db,Settings('development','dock-secret',url))) as c:
        c.db=db
        yield c
    db.dispose()


def start():
    return datetime.now(timezone.utc).replace(microsecond=0)+timedelta(days=2)


def door(client,h,w,code='DOCK-A',purpose='both'):
    r=client.post('/api/dock/doors',headers=h,json={'warehouse_id':w,'code':code,'purpose':purpose})
    assert r.status_code==201,r.text
    return r.json()['id']


def booking(client,h,w,d,start_at=None,end_at=None,key='test-booking-001',**options):
    a=start_at or start()
    b=end_at or a+timedelta(hours=1)
    payload={'warehouse_id':w,'door_id':d,'direction':'inbound','reference':'ASN-77',
         'start_at':a if isinstance(a,str) else a.isoformat(),'end_at':b if isinstance(b,str) else b.isoformat(),'carrier':'Local carrier'}
    payload.update(options)
    return client.post('/api/dock/appointments',headers={**h,'Idempotency-Key':key},json=payload)


def test_full_dock_lifecycle_and_no_inventory_mutation(client):
    h=register(client)
    w=client.get('/api/warehouses').json()[0]['id']
    d=door(client,h,w)
    with client.db.SessionLocal() as s:
        before=s.scalar(select(func.count(StockLevel.id)))
    created=booking(client,h,w,d)
    assert created.status_code==201,created.text
    aid=created.json()['id']
    assert booking(client,h,w,d).json()['replayed'] is True
    assert len(client.get('/api/dock/appointments').json())==1
    assert client.get('/api/dock/metrics').json()['scheduled']==1
    assert client.post(f'/api/dock/appointments/{aid}/complete',headers=h,json={}).status_code==409
    assert client.post(f'/api/dock/appointments/{aid}/check-in',headers=h,json={}).json()['status']=='checked_in'
    assert client.get('/api/dock/metrics').json()['checked_in']==1
    assert client.post(f'/api/dock/appointments/{aid}/cancel',headers=h,json={'note':'no'}).status_code==409
    assert client.post(f'/api/dock/appointments/{aid}/complete',headers=h,json={}).json()['status']=='completed'
    assert client.post(f'/api/dock/appointments/{aid}/complete',headers=h,json={}).status_code==409
    assert client.get('/api/dock/metrics').json()['completed']==1
    assert [e['action'] for e in client.get(f'/api/dock/appointments/{aid}/events').json()]==['scheduled','checked_in','completed']
    with client.db.SessionLocal() as s:
        assert s.scalar(select(func.count(StockLevel.id)))==before
        assert s.scalar(select(func.count(DockAppointmentEvent.id)))==3


def test_conflicts_and_adjacent_windows(client):
    h=register(client)
    w=client.get('/api/warehouses').json()[0]['id']
    d=door(client,h,w)
    a=start()
    assert booking(client,h,w,d,start_at=a,key='test-booking-001').status_code==201
    assert booking(client,h,w,d,start_at=a+timedelta(minutes=30),end_at=a+timedelta(minutes=90),key='test-booking-002').status_code==409
    assert booking(client,h,w,d,start_at=a+timedelta(hours=1),end_at=a+timedelta(hours=2),key='test-booking-003').status_code==201
    future=(a+timedelta(minutes=30)).isoformat()
    r=client.get(f'/api/dock/doors/{d}/availability',params={'start_at':future,'end_at':(a+timedelta(minutes=45)).isoformat()})
    assert r.json()['available'] is False and len(r.json()['conflicts'])==1
    assert client.get('/api/dock/metrics').json()['scheduled']==2


def test_cancel_releases_reservation_and_requires_note(client):
    h=register(client)
    w=client.get('/api/warehouses').json()[0]['id'];d=door(client,h,w)
    r=booking(client,h,w,d); aid=r.json()['id']
    assert client.post(f'/api/dock/appointments/{aid}/cancel',headers=h,json={}).status_code==400
    assert client.post(f'/api/dock/appointments/{aid}/cancel',headers=h,json={'note':'Wrong truck'}).json()['status']=='canceled'
    assert booking(client,h,w,d,key='test-booking-002').status_code==201
    assert client.get('/api/dock/metrics').json()['canceled']==1


def test_retry_conflict_tenant_and_door_direction(client):
    h=register(client)
    w=client.get('/api/warehouses').json()[0]['id'];d=door(client,h,w,purpose='inbound')
    assert booking(client,h,w,d,direction='outbound').status_code==409
    assert booking(client,h,w,d).status_code==201
    assert booking(client,h,w,d,reference='CHANGED').status_code==409
    assert booking(client,h,w,d,key='short').status_code==400
    assert client.post('/api/dock/appointments',json={}).status_code in (401,403,422)
    h2=register(client,'Other dock tenant','other-docks@example.com')
    assert client.get('/api/dock/doors').json()==[]
    assert client.get('/api/dock/appointments').json()==[]
    assert client.get(f'/api/dock/appointments/1/events').status_code==404
    w2=client.get('/api/warehouses').json()[0]['id']
    assert booking(client,h2,w2,d,key='other-key-222').status_code==404
    assert client.get(f'/api/dock/doors/{d}/availability',params={'start_at':start().isoformat(),'end_at':(start()+timedelta(hours=1)).isoformat()}).status_code==404


def test_temporal_validation_status_and_no_show(client):
    h=register(client)
    w=client.get('/api/warehouses').json()[0]['id'];d=door(client,h,w)
    a=start()
    assert booking(client,h,w,d,start_at=a,end_at=a+timedelta(minutes=5)).status_code==400
    assert booking(client,h,w,d,start_at=a,end_at=a+timedelta(days=2)).status_code==400
    assert booking(client,h,w,d,start_at=a.isoformat().replace('+00:00',''),end_at=(a+timedelta(hours=1)).isoformat()).status_code==400
    aid=booking(client,h,w,d).json()['id']
    assert client.post(f'/api/dock/appointments/{aid}/no-show',headers=h,json={'note':'Not arrived'}).status_code==409
    assert client.get('/api/dock/appointments?status=invalid').status_code==400
    assert client.get('/api/dock/appointments?limit=201').status_code==422
    assert client.get('/api/dock/appointments?warehouse_id=999999').status_code==404


def test_operator_access_requires_manager_to_reserve(client):
    h=register(client)
    w=client.get('/api/warehouses').json()[0]['id'];d=door(client,h,w)
    aid=booking(client,h,w,d).json()['id']
    with client.db.SessionLocal() as s:
        user=s.scalar(select(User).where(User.email=='owner@example.com'))
        user.role='staff'
        s.commit()
    assert client.post('/api/dock/doors',headers=h,json={'warehouse_id':w,'code':'B'}).status_code==403
    assert booking(client,h,w,d,key='other-key-222').status_code==403
    assert client.post(f'/api/dock/appointments/{aid}/cancel',headers=h,json={'note':'No'}).status_code==403
    assert client.post(f'/api/dock/appointments/{aid}/check-in',headers=h,json={}).status_code==200
    assert client.post(f'/api/dock/appointments/{aid}/complete',headers=h,json={}).status_code==200
    assert client.get('/api/dock/appointments').status_code==200


def test_schedule_has_visible_dashboard_controls(client):
    h=register(client)
    r=client.get('/app')
    assert r.status_code==200
    assert 'dock-scheduler' in r.text and 'dock-book-form' in r.text
    assert client.get('/static/dock_scheduler.js').status_code==200


def test_no_show_after_start_and_isolated_door_codes(client):
    h=register(client)
    w=client.get('/api/warehouses').json()[0]['id']
    first=door(client,h,w)
    assert client.post('/api/dock/doors',headers=h,json={'warehouse_id':w,'code':'dock-a'}).status_code==409
    appt=booking(client,h,w,first).json()['id']
    with client.db.SessionLocal() as s:
        x=s.scalar(select(DockAppointment).where(DockAppointment.id==appt))
        x.start_at=datetime.now(timezone.utc)-timedelta(minutes=10)
        s.commit()
    r=client.post(f'/api/dock/appointments/{appt}/no-show',headers=h,json={'note':'Vehicle never arrived'})
    assert r.status_code==200,r.text
    assert r.json()['status']=='no_show'
    assert client.get('/api/dock/metrics').json()['no_show']==1
    assert booking(client,h,w,first,key='new-no-show-booking').status_code==201
