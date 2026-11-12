from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from tests_web.test_warehouse_web import register, add_stock


@pytest.fixture
def client(tmp_path):
    url=f"sqlite:///{tmp_path / 'pick.sqlite3'}"
    db=Database(url)
    with TestClient(create_app(db, Settings('development','pick-test-secret',url))) as c:yield c
    db.dispose()


def test_pick_list_is_read_only_and_contains_order_details(client):
    h=register(client)
    warehouse=add_stock(client,h,'PICK-1',10)
    order=client.post('/api/orders',headers=h,json={
        'warehouse_id':warehouse,'customer_name':'Sample Retail Buyer',
        'due_date':(date.today()+timedelta(days=3)).isoformat(),
        'items':[{'sku':'PICK-1','quantity':3}]}).json()['id']
    before=client.get('/api/inventory').json()
    r=client.get(f'/api/orders/{order}/pick-list')
    assert r.status_code==200
    assert r.json()['customer']=='Sample Retail Buyer'
    assert r.json()['items']==[{'sku':'PICK-1','name':'Sample Product','unit':'each','quantity':3}]
    assert client.get('/api/inventory').json()==before


def test_pick_list_requires_login_and_tenant_membership(client):
    assert client.get('/api/orders/123/pick-list').status_code==401
    h=register(client)
    assert client.get('/api/orders/123/pick-list').status_code==404
