"""Critical case queue and manual shipment milestones with cross-tenant boundaries."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from dispatchforge_app.models import WarehouseException, ShipmentTrackingUpdate, User
from tests_web.test_inbound_notices import purchase, notice, scan
from tests_web.test_outbound_execution import ready, plan, picked, carton, pack, dispatch
from tests_web.test_warehouse_web import register


@pytest.fixture
def client(tmp_path):
    url=f"sqlite:///{tmp_path/'ops.sqlite3'}"
    db=Database(url)
    with TestClient(create_app(db,Settings('development','ops-secret',url))) as c:
        c.test_db=db
        yield c
    db.dispose()


def case_open(client,headers,warehouse_id,key='manual-case-0001',**overrides):
    payload={'warehouse_id':warehouse_id,'category':'manual','severity':'high',
        'title':'Blocked receiving dock','detail':'Scanner is offline',
        'source_type':'manual','source_id':None}
    payload.update(overrides)
    return client.post('/api/exceptions',headers={**headers,'Idempotency-Key':key},json=payload)


def test_case_lifecycle_with_sla_assign_ack_comment_resolve_reopen(client):
    h=register(client)
    w=client.get('/api/warehouses').json()[0]['id']
    result=case_open(client,h,w)
    assert result.status_code==201,result.text
    cid=result.json()['id']
    assert case_open(client,h,w).json()['replayed'] is True
    assert case_open(client,h,w,key='manual-case-0001',title='Changed').status_code==409
    assert case_open(client,h,w,key='bad').status_code==400
    with client.test_db.SessionLocal() as s:
        uid=s.scalar(select(User.id).where(User.email=='owner@example.com',User.role=='owner'))
    result=client.post(f'/api/exceptions/{cid}/assign',headers=h,json={'user_id':uid})
    assert result.status_code==200,result.text
    assert client.post(f'/api/exceptions/{cid}/acknowledge',headers=h).json()['status']=='acknowledged'
    assert client.post(f'/api/exceptions/{cid}/notes',headers=h,json={'note':'Supplier notified'}).status_code==200
    assert client.post(f'/api/exceptions/{cid}/resolve',headers=h,json={'note':'no'}).status_code==400
    assert client.post(f'/api/exceptions/{cid}/resolve',headers=h,json={'note':'Scanner swapped'}).json()['status']=='resolved'
    assert client.post(f'/api/exceptions/{cid}/acknowledge',headers=h).status_code==409
    assert client.post(f'/api/exceptions/{cid}/reopen',headers=h,json={'note':'Issue returned'}).json()['status']=='open'
    actions=[e['action'] for e in client.get(f'/api/exceptions/{cid}/events').json()]
    assert actions==['opened','assigned','acknowledged','commented','resolved','reopened']
    entries=client.get('/api/exceptions?status=open&severity=high').json()
    assert len(entries)==1 and entries[0]['id']==cid
    assert 'overdue' in entries[0] and 'due_at' in entries[0]


def test_cross_tenant_case_source_and_csrf(client):
    h=register(client)
    w=client.get('/api/warehouses').json()[0]['id']
    cid=case_open(client,h,w).json()['id']
    assert case_open(client,h,w,key='case-other-0001',source_type='shipment',
        source_id=999).status_code==404
    assert client.post('/api/exceptions',json={'warehouse_id':w,'title':'No CSRF'}).status_code==403
    other=register(client,'Second Tenant','second-ops@example.com')
    assert client.get('/api/exceptions').json()==[]
    assert client.get(f'/api/exceptions/{cid}/events').status_code==404
    assert client.post(f'/api/exceptions/{cid}/resolve',headers=other,
        json={'note':'Hijack case'}).status_code==404
    assert case_open(client,other,w,key='cross-tenant-001').status_code==404


def test_inbound_damage_and_shortage_create_actionable_cases(client):
    h,w,po,po_line=purchase(client)
    asn=notice(client,h,po,po_line).json()['id']
    line=client.get('/api/inbound/notices').json()[0]['items'][0]['id']
    client.post(f'/api/inbound/notices/{asn}/arrive',headers=h)
    assert scan(client,h,asn,line,accepted=5,damaged=2,
        damage_note='Broken during unloading').status_code==200
    assert scan(client,h,asn,line,accepted=5,damaged=2,
        damage_note='Broken during unloading').json()['replayed'] is True
    assert client.post(f'/api/inbound/notices/{asn}/close',headers=h,
        json={'note':'Five units missing in transit'}).status_code==200
    cases=client.get('/api/exceptions').json()
    assert sorted(c['category'] for c in cases)==['inbound_damage','inbound_shortage']
    assert all(c['source_id']==asn and c['source_type']=='inbound_notice' for c in cases)
    assert client.get('/api/inventory').json()[0]['on_hand']==5
    assert client.get('/api/operations/metrics').json()['open_exceptions']==2
    with client.test_db.SessionLocal() as s:
        assert s.scalar(select(func.count(WarehouseException.id)))==2


def test_manual_shipping_events_do_not_change_ledger_and_manifest_is_verified(client):
    h,w,b,oid,line=ready(client)
    p=plan(client,h,oid,line,b).json()['id']
    assert picked(client,h,p).status_code==200
    cid=carton(client,h,oid)
    assert pack(client,h,cid,p).status_code==200
    assert client.get(f'/api/outbound/orders/{oid}/manifest.csv').status_code==409
    assert client.post(f'/api/outbound/cartons/{cid}/seal',headers=h).status_code==200
    manifest=client.get(f'/api/outbound/orders/{oid}/manifest.csv')
    assert manifest.status_code==200 and 'PRODUCT-1' in manifest.text and 'PACK-001' in manifest.text
    ship=dispatch(client,h,oid)
    assert ship.status_code==200,ship.text
    ship_id=ship.json()['id']
    base_inv=client.get('/api/inventory').json()[0]['on_hand']
    url=f'/api/shipping/shipments/{ship_id}/events'
    hdr={**h,'Idempotency-Key':'carrier-milestone-001'}
    posted=client.post(url,headers=hdr,json={'milestone':'in_transit','location':'Houston Hub'})
    assert posted.status_code==201,posted.text
    assert posted.json()['source']=='manual_operator_entry'
    assert client.post(url,headers=hdr,json={'milestone':'in_transit','location':'Houston Hub'}).json()['replayed'] is True
    assert client.post(url,headers=hdr,json={'milestone':'delivered'}).status_code==409
    assert client.post(url,headers={**h,'Idempotency-Key':'carrier-milestone-002'},
        json={'milestone':'delayed'}).status_code==400
    assert client.post(url,headers={**h,'Idempotency-Key':'carrier-milestone-003'},
        json={'milestone':'delivered','note':'Warehouse manually reported receipt'}).status_code==201
    assert client.post(url,headers={**h,'Idempotency-Key':'carrier-milestone-004'},
        json={'milestone':'in_transit'}).status_code==409
    assert client.get('/api/shipping/tracking').json()[0]['milestone']=='delivered'
    assert [row['shipment_id'] for row in client.get(f'/api/shipping/tracking?warehouse_id={w}').json()]==[ship_id]
    assert client.get('/api/shipping/tracking?warehouse_id=999999').json()==[]
    assert client.get('/api/shipping/tracking?warehouse_id=-1').status_code==422
    assert client.get('/api/shipping/tracking').json()[0]['verified_by_carrier'] is False
    # Listing must fetch the latest milestones with one bounded query, not N+1.
    event_queries=[]
    def observe(_conn, _cursor, statement, _params, _ctx, _many):
        if statement.lstrip().lower().startswith('select') and 'shipment_tracking_updates' in statement:
            event_queries.append(statement)
    event.listen(client.test_db.engine,'before_cursor_execute',observe)
    try:
        assert client.get('/api/shipping/tracking').status_code==200
    finally:
        event.remove(client.test_db.engine,'before_cursor_execute',observe)
    assert len(event_queries)==1
    assert [x['milestone'] for x in client.get(url).json()]==['in_transit','delivered']
    assert client.get('/api/inventory').json()[0]['on_hand']==base_inv
    assert client.get('/api/operations/metrics').json()['shipped_orders']==1
    with client.test_db.SessionLocal() as s:
        assert s.scalar(select(func.count(ShipmentTrackingUpdate.id)))==2


def test_live_metrics_and_nonexistent_other_tenant_shipment(client):
    h=register(client)
    metrics=client.get('/api/operations/metrics').json()
    assert metrics['source']=='live_database_snapshot'
    assert metrics['shipped_orders']==0
    assert metrics['picked_staged_units']==0
    assert client.get('/api/shipping/shipments/123456/events').status_code==404
    assert client.post('/api/shipping/shipments/123456/events',headers={**h,'Idempotency-Key':'tracking-unauth-0001'},
        json={'milestone':'in_transit'}).status_code==404
    assert client.get('/api/operations/metrics?warehouse_id=999999').json()['warehouse_on_hand_units']==0
