from datetime import date, timedelta
import re
import pytest
from fastapi.testclient import TestClient
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from tests_web.test_warehouse_web import register, add_stock, order_request

@pytest.fixture
def client(tmp_path):
    url=f"sqlite:///{tmp_path / 'returns.sqlite3'}"
    db=Database(url)
    with TestClient(create_app(db,Settings('development','returns-secret',url))) as c:yield c
    db.dispose()


def create_fulfilled(c,h):
    wid=add_stock(c,h,'RETURN-1',20)
    order=c.post('/api/orders',headers=h,json=order_request(wid,[{'sku':'RETURN-1','quantity':7}])).json()['id']
    assert c.post(f'/api/orders/{order}/fulfill',headers=h).status_code==200
    return order


def return_order(c,h,order,qty=3,ref='RET-1'):
    return c.post('/api/returns',headers=h,json={'order_id':order,
        'sku':'RETURN-1','quantity':qty,'reference':ref,'reason':'Unopened product'})


def test_return_restock_and_duplicate_reference(client):
    h=register(client)
    order=create_fulfilled(client,h)
    assert client.get('/api/inventory').json()[0]['on_hand']==13
    first=return_order(client,h,order)
    assert first.status_code==201,first.text
    assert client.get('/api/inventory').json()[0]['on_hand']==16
    assert client.get('/api/movements').json()[0]['kind']=='customer_return'
    assert return_order(client,h,order).status_code==409
    assert client.get('/api/returns').json()[0]['reference']=='RET-1'


def test_partial_returns_cannot_exceed_original_fulfillment(client):
    h=register(client)
    order=create_fulfilled(client,h)
    assert return_order(client,h,order,5,'RET-ONE').status_code==201
    assert return_order(client,h,order,3,'RET-TWO').status_code==409
    assert return_order(client,h,order,2,'RET-THREE').status_code==201
    assert client.get('/api/inventory').json()[0]['on_hand']==20


def test_return_cannot_restock_unfulfilled_order_or_other_tenant(client):
    h=register(client)
    wid=add_stock(client,h,'RETURN-1',15)
    oid=client.post('/api/orders',headers=h,json=order_request(wid,[{'sku':'RETURN-1','quantity':3}])).json()['id']
    assert return_order(client,h,oid).status_code==409
    token=re.search(r'name="csrf-token" content="([^"]+)"',client.get('/app').text).group(1)
    client.post('/logout',data={'csrf':token},follow_redirects=False)
    other=register(client,'Other Business','other@example.com')
    assert return_order(client,other,oid).status_code==404
    assert client.get('/api/returns').json()==[]
