import pytest
from fastapi.testclient import TestClient
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from tests_web.test_warehouse_web import register, add_stock

@pytest.fixture
def client(tmp_path):
    url=f"sqlite:///{tmp_path / 'replenishment.sqlite3'}"
    db=Database(url)
    with TestClient(create_app(db,Settings('development','replenish-secret',url))) as c:yield c
    db.dispose()


def test_replenishment_recommends_target_stock_minus_available(client):
    h=register(client)
    wid=add_stock(client,h,'SKU-1',2)
    r=client.get('/api/replenishment').json()
    assert len(r)==1
    assert r[0]['reorder_point']==5
    assert r[0]['available']==2
    assert r[0]['suggested_quantity']==8
    assert r[0]['incoming']==0
    assert client.get('/api/replenishment?demo=true').status_code==200


def test_existing_supplier_order_reduces_suggested_quantity(client):
    h=register(client)
    wid=add_stock(client,h,'SKU-1',2)
    sid=client.post('/api/suppliers',headers=h,json={'name':'Supplier'}).json()['id']
    p=client.post('/api/purchase-orders',headers=h,json={
        'warehouse_id':wid,'supplier_id':sid,'reference':'PO-PENDING',
        'items':[{'sku':'SKU-1','quantity':6}]})
    assert p.status_code==201
    result=client.get('/api/replenishment').json()[0]
    assert result['incoming']==6
    assert result['suggested_quantity']==2
    assert client.get('/api/inventory').json()[0]['on_hand']==2


def test_replenishment_requires_tenant_auth(client):
    assert client.get('/api/replenishment').status_code==401


def test_replenishment_csv_export_and_formula_protection(client):
    h=register(client)
    wid=client.get('/api/warehouses').json()[0]['id']
    p=client.post('/api/products',headers=h,json={
        'sku':'X-RISK','name':'=HYPERLINK("unsafe")','reorder_point':4})
    assert p.status_code==201
    csv=client.get('/api/export/replenishment.csv')
    assert csv.status_code==200
    assert "'=HYPERLINK" in csv.text
    assert 'suggested_quantity' in csv.text
    assert client.get('/api/export/replenishment.csv?demo=true').status_code==200
