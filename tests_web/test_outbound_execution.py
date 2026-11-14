"""End-to-end outbound workflow: staging, protection, carton and atomic goods issue."""
import re
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from dispatchforge_app.models import (OutboundPick, OutboundShipment, StockLevel, StockMovement,
                                      BinStock, OutboundCartonItem)
from tests_web.test_warehouse_web import register, add_stock, order_request
from tests_web.test_warehouse_execution import endpoint, task, complete


@pytest.fixture
def client(tmp_path):
    url = f"sqlite:///{tmp_path / 'outbound.sqlite3'}"
    db = Database(url)
    with TestClient(create_app(db, Settings('development', 'outbound-secret', url))) as c:
        c.test_db = db
        yield c
    db.dispose()


def ready(client, qty=20, ordered=8):
    headers = register(client)
    wid = add_stock(client, headers, quantity=qty)
    bid = endpoint(client, headers, name='PICK-01')
    tid = task(client, headers, wid, bid, qty).json()['id']
    assert client.post(f'/api/tasks/{tid}/claim', headers=headers).status_code == 200
    assert client.post(f'/api/tasks/{tid}/start', headers=headers).status_code == 200
    assert complete(client, headers, tid, target='PICK-01').status_code == 200
    response = client.post('/api/orders', headers=headers,
                           json=order_request(wid, [{'sku':'PRODUCT-1','quantity':ordered}]))
    assert response.status_code == 201, response.text
    order_id = response.json()['id']
    line_id = client.get(f'/api/outbound/orders/{order_id}/lines').json()[0]['order_line_id']
    return headers, wid, bid, order_id, line_id


def plan(client, headers, order_id, line_id, bin_id, quantity=8, key='pick-safe-key-001'):
    return client.post(f'/api/outbound/orders/{order_id}/picks', headers={**headers, 'Idempotency-Key':key},
         json={'order_line_id':line_id, 'bin_id':bin_id, 'quantity':quantity})


def picked(client, headers, pick_id):
    assert client.post(f'/api/outbound/picks/{pick_id}/claim', headers=headers).status_code == 200
    assert client.post(f'/api/outbound/picks/{pick_id}/start', headers=headers).status_code == 200
    return client.post(f'/api/outbound/picks/{pick_id}/scan', headers=headers,
        json={'scan_sku':'PRODUCT-1', 'scan_bin':'PICK-01'})


def carton(client, headers, order_id, code='PACK-001'):
    response = client.post(f'/api/outbound/orders/{order_id}/cartons',
                           headers=headers, json={'code':code})
    assert response.status_code == 201, response.text
    return response.json()['id']


def pack(client, headers, carton_id, pick_id, code='PACK-001'):
    return client.post(f'/api/outbound/cartons/{carton_id}/pack', headers=headers,
         json={'pick_id':pick_id,'scan_sku':'PRODUCT-1','scan_carton':code})


def dispatch(client, headers, order_id, key='shipment-key-01', carrier='Manual', tracking='REF-0001'):
    return client.post(f'/api/outbound/orders/{order_id}/dispatch',
        headers={**headers,'Idempotency-Key':key},
        json={'carrier':carrier,'tracking_reference':tracking})


def test_end_to_end_scan_pack_dispatch_and_replay(client):
    h,wid,bin_id,order_id,line_id = ready(client)
    r=plan(client,h,order_id,line_id,bin_id)
    assert r.status_code == 201,r.text
    pick_id=r.json()['id']
    assert plan(client,h,order_id,line_id,bin_id).json() == {'id':pick_id,'status':'queued','replayed':True}
    assert client.get('/api/locations/stock').json()[0]['committed_to_moves']==8
    assert picked(client,h,pick_id).json()['status']=='picked'
    assert client.post(f'/api/outbound/picks/{pick_id}/scan', headers=h,
        json={'scan_sku':'PRODUCT-1','scan_bin':'PICK-01'}).json()['replayed'] is True
    loc=client.get('/api/locations/reconciliation').json()[0]
    assert (loc['on_hand'],loc['placed'],loc['staged_outbound'],loc['free_unlocated'])==(20,12,8,0)
    assert dispatch(client,h,order_id).status_code==409
    carton_id=carton(client,h,order_id)
    assert pack(client,h,carton_id,pick_id).json()['status']=='packed'
    assert pack(client,h,carton_id,pick_id).json()['replayed'] is True
    assert dispatch(client,h,order_id).status_code==409
    assert client.post(f'/api/outbound/cartons/{carton_id}/seal',headers=h).json()['status']=='sealed'
    done=dispatch(client,h,order_id)
    assert done.status_code == 200,done.text
    assert done.json()['replayed'] is False
    again=dispatch(client,h,order_id)
    assert again.json()['id']==done.json()['id'] and again.json()['replayed'] is True
    assert dispatch(client,h,order_id,key='shipment-key-02').status_code==409
    inv=client.get('/api/inventory').json()[0]
    assert (inv['on_hand'],inv['reserved'])==(12,0)
    loc=client.get('/api/locations/reconciliation').json()[0]
    assert (loc['placed'],loc['staged_outbound'],loc['free_unlocated'])==(12,0,0)
    assert client.get('/api/orders').json()[0]['status']=='fulfilled'
    assert client.get('/api/outbound/cartons').json()[0]['status']=='shipped'
    assert client.get('/api/outbound/shipments').json()[0]['tracking_reference']=='REF-0001'
    with client.test_db.SessionLocal() as s:
        assert s.scalar(select(func.count(OutboundShipment.id)))==1
        assert s.scalar(select(func.count(StockMovement.id)).where(StockMovement.kind=='ship'))==1
        assert s.scalar(select(func.count(OutboundCartonItem.id)))==1


def test_overallocation_and_idempotency_conflicts(client):
    h,wid,bin_id,order_id,line_id=ready(client)
    assert plan(client,h,order_id,line_id,bin_id,6).status_code==201
    assert plan(client,h,order_id,line_id,bin_id,3,key='pick-safe-key-002').status_code==409
    assert plan(client,h,order_id,line_id,bin_id,5).status_code==409
    assert plan(client,h,order_id,line_id,bin_id,2,key='pick-safe-key-003').status_code==201
    assert client.get('/api/locations/stock').json()[0]['committed_to_moves']==8
    assert client.get(f'/api/outbound/orders/{order_id}/lines').json()[0]['planned']==8


def test_cancel_releases_bin_commitment_and_unblocks_legacy_cancel(client):
    h,wid,bin_id,order_id,line_id=ready(client)
    p=plan(client,h,order_id,line_id,bin_id).json()['id']
    assert client.post(f'/api/orders/{order_id}/cancel',headers=h).status_code==409
    assert client.post(f'/api/outbound/picks/{p}/cancel',headers=h).status_code==200
    assert client.post(f'/api/outbound/picks/{p}/cancel',headers=h).status_code==409
    assert client.get('/api/locations/stock').json()[0]['committed_to_moves']==0
    assert client.post(f'/api/orders/{order_id}/cancel',headers=h).status_code==200
    assert client.get('/api/inventory').json()[0]['reserved']==0


def test_staged_units_protected_against_unrelated_reducers(client):
    h,wid,bin_id,order_id,line_id=ready(client)
    p=plan(client,h,order_id,line_id,bin_id).json()['id']
    assert picked(client,h,p).status_code==200
    assert client.post('/api/stock/adjust',headers=h,json={
        'warehouse_id':wid,'sku':'PRODUCT-1','delta':-1}).status_code==409
    # Unlike a loose UNLOCATED pool, staged order stock cannot be put away again.
    extra_bin=endpoint(client,h,name='OTHER-01')
    assert task(client,h,wid,extra_bin,1,key='putaway-after-pick-01').status_code==409
    assert client.post(f'/api/orders/{order_id}/fulfill',headers=h).status_code==409
    assert client.get('/api/inventory').json()[0]['on_hand']==20


def test_invalid_scan_audited_without_stock_debit(client):
    h,wid,bin_id,order_id,line_id=ready(client)
    p=plan(client,h,order_id,line_id,bin_id).json()['id']
    client.post(f'/api/outbound/picks/{p}/claim',headers=h)
    client.post(f'/api/outbound/picks/{p}/start',headers=h)
    bad=client.post(f'/api/outbound/picks/{p}/scan',headers=h,
        json={'scan_sku':'OTHER','scan_bin':'PICK-01'})
    assert bad.status_code==409
    assert client.get('/api/locations/stock').json()[0]['on_hand']==20
    assert client.get(f'/api/outbound/picks/{p}/events').json()[-1]['action']=='scan_rejected'
    good=client.post(f'/api/outbound/picks/{p}/scan',headers=h,
        json={'scan_sku':'PRODUCT-1','scan_bin':'PICK-01'})
    assert good.status_code==200


def test_dispatch_rejects_partial_and_unsealed_orders(client):
    h,wid,bin_id,order_id,line_id=ready(client,ordered=10)
    p=plan(client,h,order_id,line_id,bin_id,5).json()['id']
    picked(client,h,p)
    c=carton(client,h,order_id)
    assert pack(client,h,c,p).status_code==200
    assert client.post(f'/api/outbound/cartons/{c}/seal',headers=h).status_code==200
    r=dispatch(client,h,order_id)
    assert r.status_code==409
    assert client.get('/api/inventory').json()[0]['reserved']==10
    assert client.get('/api/orders').json()[0]['status']=='reserved'


def test_missing_auth_csrf_and_cross_tenant_ids(client):
    h,wid,bin_id,order_id,line_id=ready(client)
    assert plan(client,{},order_id,line_id,bin_id).status_code==403
    p=plan(client,h,order_id,line_id,bin_id).json()['id']
    c=carton(client,h,order_id)
    assert client.post(f'/api/outbound/picks/{p}/claim').status_code==403
    assert client.post(f'/api/outbound/cartons/{c}/seal',headers=h).status_code==409
    csrf=re.search(r'name="csrf-token" content="([^"]+)"',client.get('/app').text).group(1)
    client.post('/logout',data={'csrf':csrf},follow_redirects=False)
    h2=register(client,'Other Company','other-outbound@example.com')
    assert client.get(f'/api/outbound/orders/{order_id}/lines').status_code==404
    assert client.get(f'/api/outbound/picks/{p}/events').status_code==404
    assert client.post(f'/api/outbound/picks/{p}/claim',headers=h2).status_code==404
    assert client.post(f'/api/outbound/cartons/{c}/seal',headers=h2).status_code==404
    assert dispatch(client,h2,order_id).status_code==404
    assert client.get('/api/outbound/picks').json()==[]
