"""Inbound ASN receipt flows: exact purchase-line binding, damage and safe retries."""
import pytest
from fastapi.testclient import TestClient
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from tests_web.test_purchasing import register, setup, create


@pytest.fixture
def client(tmp_path):
    url = f"sqlite:///{tmp_path / 'asn.sqlite3'}"
    db = Database(url)
    with TestClient(create_app(db, Settings('development','asn-test-key',url))) as c:
        yield c
    db.dispose()


def purchase(client):
    headers = register(client)
    wid, supplier = setup(client, headers)
    po = create(client, headers, wid, supplier)
    assert po.status_code == 201
    line_id = client.get('/api/purchase-orders').json()[0]['items'][0]['line_id']
    return headers, wid, po.json()['id'], line_id


def notice(client, headers, po_id, line_id, expected=12, ref='ASN-001'):
    return client.post('/api/inbound/notices',headers=headers,json={
        'purchase_order_id':po_id,'reference':ref,'supplier_reference':'SUP-PO-17',
        'dock':'D-02','items':[{'purchase_line_id':line_id,'expected':expected}]})


def scan(client, headers, notice_id, line_id, accepted=5, damaged=0,
         key='asn-scan-0001', sku='WIDGET', damage_note=''):
    return client.post(f'/api/inbound/notices/{notice_id}/scan',headers={
        **headers,'Idempotency-Key':key},json={'line_id':line_id,'scan_sku':sku,
        'accepted':accepted,'damaged':damaged,'damage_note':damage_note})


def test_inbound_dock_receive_damaged_short_and_replay(client):
    h, wid, po, po_line = purchase(client)
    r = notice(client,h,po,po_line)
    assert r.status_code == 201,r.text
    asn = r.json()['id']
    line = client.get('/api/inbound/notices').json()[0]['items'][0]['id']
    assert scan(client,h,asn,line).status_code == 409
    assert client.post(f'/api/inbound/notices/{asn}/arrive',headers=h).json()['status']=='arrived'
    assert client.post(f'/api/inbound/notices/{asn}/arrive',headers=h).json()['replayed'] is True
    got=scan(client,h,asn,line,5,2,damage_note='Damaged packaging')
    assert got.status_code == 200,got.text
    assert (got.json()['accepted'],got.json()['damaged']) == (5,2)
    again=scan(client,h,asn,line,5,2,damage_note='Damaged packaging')
    assert again.status_code==200 and again.json()['replayed'] is True
    assert client.get('/api/inventory').json()[0]['on_hand']==5
    assert client.get('/api/purchase-orders').json()[0]['items'][0]['received']==5
    assert len(client.get(f'/api/inbound/notices/{asn}/receipts').json()) == 1
    assert client.get('/api/inbound/notices').json()[0]['short'] == 5
    assert client.post(f'/api/inbound/notices/{asn}/close',headers=h,json={'note':''}).status_code==409
    closed=client.post(f'/api/inbound/notices/{asn}/close',headers=h,json={'note':'Supplier short-loaded pallet'})
    assert closed.status_code==200 and closed.json()['short']==5
    assert scan(client,h,asn,line,1,key='asn-scan-0002').status_code==409
    assert [e['action'] for e in client.get(f'/api/inbound/notices/{asn}/events').json()] == [
        'planned','arrived','receipt','closed']


def test_receive_full_without_shortage_and_preserve_po_movements(client):
    h,w,po,p_line = purchase(client)
    asn = notice(client,h,po,p_line).json()['id']
    l = client.get('/api/inbound/notices').json()[0]['items'][0]['id']
    client.post(f'/api/inbound/notices/{asn}/arrive',headers=h)
    assert scan(client,h,asn,l,accepted=12).status_code==200
    assert client.post(f'/api/inbound/notices/{asn}/close',headers=h,json={}).json()['short']==0
    assert client.get('/api/purchase-orders').json()[0]['status']=='received'
    assert sum(m['on_hand_delta'] for m in client.get('/api/movements').json() if m['kind']=='purchase_receipt')==12


def test_inbound_scan_validation_and_atomic_stock_protection(client):
    h,w,po,p_line=purchase(client)
    asn=notice(client,h,po,p_line).json()['id']
    l=client.get('/api/inbound/notices').json()[0]['items'][0]['id']
    client.post(f'/api/inbound/notices/{asn}/arrive',headers=h)
    assert scan(client,h,asn,l,accepted=3,damaged=1,key='asn-bad-00001',sku='WRONG',
                damage_note='Broken').status_code==409
    assert scan(client,h,asn,l,accepted=0,damaged=1,key='asn-bad-00002').status_code==400
    assert scan(client,h,asn,l,accepted=13,key='asn-bad-00003').status_code==409
    assert scan(client,h,asn,l,accepted=5,key='asn-good-0001').status_code==200
    assert scan(client,h,asn,l,accepted=4,key='asn-good-0001').status_code==409
    assert scan(client,h,asn,l,accepted=8,key='asn-good-0002').status_code==409
    assert scan(client,h,asn,l,accepted=7,key='asn-good-0003').status_code==200
    assert client.get('/api/inventory').json()[0]['on_hand']==12
    assert len(client.get(f'/api/inbound/notices/{asn}/receipts').json())==2


def test_tenant_boundary_and_plan_capacity_and_cancellation(client):
    h,w,po,p_line=purchase(client)
    asn=notice(client,h,po,p_line,expected=7).json()['id']
    assert notice(client,h,po,p_line,expected=6,ref='ASN-002').status_code==409
    assert notice(client,h,po,p_line,expected=5,ref='ASN-002').status_code==201
    assert notice(client,h,po,p_line,expected=1,ref='ASN-003').status_code==409
    assert client.post(f'/api/inbound/notices/{asn}/cancel',headers=h,json={'note':'Canceled'}).status_code==200
    assert notice(client,h,po,p_line,expected=7,ref='ASN-004').status_code==201
    other_h=register(client,'Another Warehouse','other-inbound@example.com')
    assert client.get('/api/inbound/notices').json() == []
    assert client.get(f'/api/inbound/notices/{asn}/events').status_code==404
    assert client.post(f'/api/inbound/notices/{asn}/arrive',headers=other_h).status_code==404
    assert notice(client,other_h,po,p_line,expected=1,ref='EXTERNAL').status_code==404


def test_receipts_protect_against_cancellation_and_csrf(client):
    h,w,po,p_line = purchase(client)
    asn=notice(client,h,po,p_line).json()['id']
    l=client.get('/api/inbound/notices').json()[0]['items'][0]['id']
    assert client.post(f'/api/inbound/notices/{asn}/arrive').status_code == 403
    client.post(f'/api/inbound/notices/{asn}/arrive',headers=h)
    scan(client,h,asn,l,accepted=1)
    assert client.post(f'/api/inbound/notices/{asn}/cancel',headers=h,json={}).status_code==409
    assert len(client.get('/api/inbound/notices').json())==1
