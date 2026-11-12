import pytest
from fastapi.testclient import TestClient
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from tests_web.test_warehouse_web import register, add_stock

@pytest.fixture
def client(tmp_path):
    url=f"sqlite:///{tmp_path / 'audit.sqlite3'}"
    db=Database(url)
    with TestClient(create_app(db,Settings('development','audit-secret',url))) as c:yield c
    db.dispose()


def test_audit_filter_and_cursor_pagination(client):
    h=register(client)
    w=add_stock(client,h,'AUDIT-SKU',10)
    for i in range(5):
        r=client.post('/api/stock/receive',headers=h,json={
            'warehouse_id':w,'sku':'AUDIT-SKU','quantity':1,'note':f'batch-{i}'})
        assert r.status_code==200
    first=client.get('/api/audit?limit=3').json()
    assert len(first['items'])==3
    assert first['next_cursor'] is not None
    second=client.get('/api/audit',params={'limit':3,'before_id':first['next_cursor']}).json()
    assert len(second['items'])==3
    assert {r['id'] for r in first['items']}.isdisjoint(r['id'] for r in second['items'])
    assert client.get('/api/audit?kind=transfer_in').json()['items']==[]
    assert len(client.get('/api/audit?sku=AUDIT-SKU').json()['items'])==6
    assert client.get('/api/audit?limit=201').status_code==422


def test_audit_never_exposes_other_warehouse_business(client):
    h=register(client)
    w=add_stock(client,h,'ONLY-OWN',8)
    assert client.get('/api/audit').json()['items'][0]['sku']=='ONLY-OWN'
    assert client.get('/api/audit?demo=true').status_code==200
    assert client.get('/api/audit?warehouse_id=99999').json()['items']==[]
