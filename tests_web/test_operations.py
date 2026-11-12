from datetime import date, timedelta
import re
import pytest
from fastapi.testclient import TestClient
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from tests_web.test_warehouse_web import register, add_stock

@pytest.fixture
def client(tmp_path):
    url=f"sqlite:///{tmp_path / 'operations.sqlite3'}"
    db=Database(url)
    with TestClient(create_app(db,Settings('development','operations-secret',url))) as c:yield c
    db.dispose()


def test_queue_groups_scheduled_fulfillment_and_purchase_orders(client):
    h=register(client)
    w=add_stock(client,h,'QUEUED',10)
    due=(date.today()+timedelta(days=2)).isoformat()
    assert client.post('/api/orders',headers=h,json={
        'warehouse_id':w,'customer_name':'Operations Buyer','due_date':due,
        'items':[{'sku':'QUEUED','quantity':2}]}).status_code==201
    supplier=client.post('/api/suppliers',headers=h,json={'name':'Incoming Vendor'}).json()['id']
    po=client.post('/api/purchase-orders',headers=h,json={
        'warehouse_id':w,'supplier_id':supplier,'reference':'PO-QUEUE',
        'expected_date':due,'items':[{'sku':'QUEUED','quantity':5}]})
    assert po.status_code==201
    queue=client.get('/api/operations/queue').json()
    assert queue['outgoing_orders'][0]['customer']=='Operations Buyer'
    assert queue['incoming_purchases'][0]['reference']=='PO-QUEUE'
    assert queue['overdue_outgoing']==0
    assert client.get('/api/operations/queue?days=91').status_code==422
    assert 'data-view="planning"' in client.get('/app').text


def test_planning_requires_login_and_is_tenant_scoped(client):
    assert client.get('/api/operations/queue').status_code==401
    h=register(client)
    assert client.get('/api/operations/queue').json()['outgoing_orders']==[]
    assert client.get('/api/operations/queue?demo=true').status_code==200
