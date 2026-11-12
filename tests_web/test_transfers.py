"""Transfer tests cover stock integrity, roles, audit trails and tenant boundaries."""
import pytest
from fastapi.testclient import TestClient
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from tests_web.test_warehouse_web import register, add_stock


@pytest.fixture
def client(tmp_path):
    url = f"sqlite:///{tmp_path / 'transfers.sqlite3'}"
    db = Database(url)
    with TestClient(create_app(db, Settings("development", "transfer-test-secret", url))) as c:
        yield c
    db.dispose()


def setup(c):
    h = register(c)
    a = add_stock(c, h, "WATER", 20)
    b = c.post('/api/warehouses', headers=h, json={'name': 'Second Warehouse'}).json()['id']
    return h, a, b


def transfer(c, h, a, b, qty=5):
    return c.post('/api/transfers', headers=h, json={
        'source_warehouse_id': a, 'destination_warehouse_id': b,
        'sku': 'WATER', 'quantity': qty, 'note': 'Scheduled move'})


def test_transfer_moves_stock_without_changing_total(client):
    h, a, b = setup(client)
    assert transfer(client, h, a, b).status_code == 201
    inventory = client.get('/api/inventory').json()
    assert {row['warehouse_id']: row['on_hand'] for row in inventory} == {a:15,b:5}
    assert sum(row['on_hand'] for row in inventory) == 20
    kinds = {x['kind'] for x in client.get('/api/movements').json()}
    assert {'transfer_in','transfer_out'} <= kinds
    assert client.get('/api/transfers').json()[0]['quantity'] == 5


def test_transfer_refuses_reserved_units_and_self_transfer(client):
    h, a, b = setup(client)
    assert client.post('/api/orders', headers=h, json={
        'warehouse_id': a, 'customer_name':'Buyer', 'due_date':'2099-01-01',
        'items':[{'sku':'WATER','quantity':18}]}).status_code == 201
    assert transfer(client,h,a,b,3).status_code == 409
    assert transfer(client,h,a,a,1).status_code == 400
    assert client.get('/api/transfers').json() == []


def test_cross_tenant_transfer_is_rejected(client):
    h, a, b = setup(client)
    import re
    token = re.search(r'name="csrf-token" content="([^"]+)"',client.get('/app').text).group(1)
    client.post('/logout',data={'csrf': token},follow_redirects=False)
    other = register(client,'Another Business','other@example.com')
    other_a = client.get('/api/warehouses').json()[0]['id']
    assert client.post('/api/products',headers=other,json={'sku':'WATER','name':'Water'}).status_code == 201
    assert transfer(client,other,a,other_a).status_code == 404
    assert client.get('/api/transfers').json() == []
    assert client.post('/api/transfers',json={'source_warehouse_id':a,
        'destination_warehouse_id':b,'sku':'WATER','quantity':1}).status_code == 403
