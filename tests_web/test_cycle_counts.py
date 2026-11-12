"""Cycle count reconciliation tests: reservations, staleness, tenant isolation."""
import re
import pytest
from fastapi.testclient import TestClient
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from tests_web.test_warehouse_web import register, add_stock, order_request

@pytest.fixture
def client(tmp_path):
    url=f"sqlite:///{tmp_path / 'counts.sqlite3'}"
    db=Database(url)
    with TestClient(create_app(db,Settings('development','count-secret',url))) as c:yield c
    db.dispose()


def start(c,h,warehouse,sku='COUNTS'):
    return c.post('/api/cycle-counts',headers=h,json={
        'warehouse_id':warehouse,'sku':sku,'note':'Weekly physical count'})


def test_post_count_reconciles_and_audits_difference(client):
    h=register(client)
    w=add_stock(client,h,'COUNTS',20)
    count=start(client,h,w).json()
    assert count['expected_on_hand']==20
    assert client.get('/api/inventory').json()[0]['on_hand']==20
    posted=client.post(f'/api/cycle-counts/{count["id"]}/post',headers=h,
                       json={'counted_on_hand':18})
    assert posted.status_code==200,posted.text
    assert client.get('/api/inventory').json()[0]['on_hand']==18
    assert client.get('/api/movements').json()[0]['on_hand_delta']==-2
    assert client.post(f'/api/cycle-counts/{count["id"]}/post',headers=h,
        json={'counted_on_hand':18}).status_code==409


def test_stale_count_cannot_overwrite_new_receipt(client):
    h=register(client)
    w=add_stock(client,h,'COUNTS',20)
    count=start(client,h,w).json()['id']
    assert client.post('/api/stock/receive',headers=h,json={
        'warehouse_id':w,'sku':'COUNTS','quantity':2}).status_code==200
    assert client.post(f'/api/cycle-counts/{count}/post',headers=h,
                       json={'counted_on_hand':19}).status_code==409
    assert client.get('/api/inventory').json()[0]['on_hand']==22
    assert client.get('/api/cycle-counts').json()[0]['status']=='open'


def test_count_cannot_write_off_reserved_stock(client):
    h=register(client)
    w=add_stock(client,h,'COUNTS',20)
    order=client.post('/api/orders',headers=h,json=order_request(w,[{'sku':'COUNTS','quantity':15}]))
    assert order.status_code==201
    count=start(client,h,w).json()['id']
    assert client.post(f'/api/cycle-counts/{count}/post',headers=h,
                       json={'counted_on_hand':14}).status_code==409
    assert client.get('/api/inventory').json()[0]['reserved']==15
    assert client.post(f'/api/cycle-counts/{count}/cancel',headers=h).json()['status']=='canceled'


def test_cross_workspace_count_is_inaccessible(client):
    h=register(client)
    w=add_stock(client,h,'COUNTS',10)
    cid=start(client,h,w).json()['id']
    token=re.search(r'name="csrf-token" content="([^"]+)"',client.get('/app').text).group(1)
    client.post('/logout',data={'csrf':token},follow_redirects=False)
    other=register(client,'Second Co','second@example.com')
    assert client.get('/api/cycle-counts').json()==[]
    assert client.post(f'/api/cycle-counts/{cid}/post',headers=other,
                       json={'counted_on_hand':5}).status_code==404
    assert client.post(f'/api/cycle-counts/{cid}/cancel',headers=other).status_code==404
