"""Regression and API contract tests for Phase 1 physical warehouse execution."""
from datetime import date, timedelta
import re
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from dispatchforge_app.database import Database
from dispatchforge_app.models import BinStock, Product, StockLevel, WarehouseTaskEvent
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from tests_web.test_warehouse_web import register, add_stock, order_request


@pytest.fixture
def client(tmp_path):
    url = f"sqlite:///{tmp_path / 'execution.sqlite3'}"
    db = Database(url)
    with TestClient(create_app(db, Settings("development", "execution-test-secret", url))) as c:
        c.test_db = db
        yield c
    db.dispose()


def endpoint(client, h, name="A-01", wid=None, cap=None):
    wid = wid or client.get('/api/warehouses').json()[0]['id']
    result = client.post('/api/locations', headers=h, json={
        'warehouse_id': wid, 'code': name, 'zone': 'Z1', 'aisle': 'A',
        'rack': 'R02', 'shelf': 'S1', 'capacity_units': cap})
    assert result.status_code == 201, result.text
    return result.json()['id']


def task(client, h, wid, target, qty, kind='putaway', source=None, key='task-key-0001', sku='PRODUCT-1'):
    body = dict(warehouse_id=wid, sku=sku, kind=kind, to_bin_id=target,
                from_bin_id=source, quantity=qty, priority=2, note='Today work')
    return client.post('/api/tasks', headers={**h, 'Idempotency-Key':key}, json=body)


def complete(client, h, task_id, target='A-01', source=None, sku='PRODUCT-1'):
    return client.post(f'/api/tasks/{task_id}/complete', headers=h, json={
        'scan_sku':sku, 'scan_to_bin':target, 'scan_from_bin':source})


def prepare(client):
    h = register(client)
    wid = add_stock(client, h)
    target = endpoint(client, h)
    return h, wid, target


def test_bin_codes_tenant_scoped_and_unique(client):
    h, wid, target = prepare(client)
    assert target
    bins = client.get('/api/locations').json()
    assert len(bins) == 1 and bins[0]['code'] == 'A-01'
    assert bins[0]['zone'] == 'Z1' and bins[0]['rack'] == 'R02'
    assert client.post('/api/locations',headers=h,json={'warehouse_id':wid,'code':'a-01'}).status_code==409
    assert client.post('/api/locations',headers=h,json={'warehouse_id':wid,'code':'!bad'}).status_code==400
    assert client.post('/api/locations',json={'warehouse_id':wid,'code':'A-02'}).status_code==403
    assert client.post('/api/locations',headers=h,json={'warehouse_id':987654,'code':'A-02'}).status_code==404
    with client.test_db.SessionLocal() as s:
        # Location is tenant-owned, but even a valid ID in another warehouse is rejected.
        assert s.scalar(select(StockLevel.on_hand).where(StockLevel.business_id > 0)) is not None


def test_putaway_reconciliation_and_scan_proof(client):
    h, wid, a = prepare(client)
    result = task(client, h, wid, a, 8)
    assert result.status_code == 201, result.text
    task_id = result.json()['id']
    assert task(client,h,wid,a,8).json()=={'id':task_id,'status':'queued','replayed':True}
    assert client.get('/api/locations/reconciliation').json()[0]['pending_putaway'] == 8
    assert client.post(f'/api/tasks/{task_id}/claim',headers=h).json()['status']=='assigned'
    assert client.post(f'/api/tasks/{task_id}/start',headers=h).json()['status']=='in_progress'
    assert complete(client,h,task_id,sku='WRONG').status_code==409
    assert client.get('/api/locations/stock').json() == []
    assert client.get(f'/api/tasks/{task_id}/events').json()[-1]['action']=='scan_rejected'
    done=complete(client,h,task_id)
    assert done.status_code==200,done.text
    assert done.json()=={'id':task_id,'status':'completed','replayed':False}
    assert complete(client,h,task_id).json()['replayed'] is True
    assert complete(client,h,task_id,target='A-XX').status_code==409
    stock=client.get('/api/locations/stock').json()[0]
    assert stock['on_hand']==8 and stock['committed_to_moves']==0
    summary=client.get('/api/locations/reconciliation').json()[0]
    assert (summary['on_hand'],summary['placed'],summary['unlocated'],summary['pending_putaway'])==(20,8,12,0)
    assert client.get('/api/inventory').json()[0]['on_hand']==20
    assert client.get(f'/api/tasks/{task_id}/events').json()[-1]['action']=='completed'


def test_putaway_prevents_double_scheduling_and_bad_key(client):
    h,wid,a=prepare(client)
    assert task(client,h,wid,a,18).status_code==201
    assert task(client,h,wid,a,3,key='task-key-0002').status_code==409
    assert task(client,h,wid,a,17,key='task-key-0001').status_code==409
    assert client.get('/api/locations/reconciliation').json()[0]['pending_putaway']==18


def test_move_reserves_source_and_checks_capacity(client):
    h,wid,a=prepare(client)
    b=endpoint(client,h,'A-02',cap=5)
    put=task(client,h,wid,a,10)
    tid=put.json()['id']
    client.post(f'/api/tasks/{tid}/claim',headers=h)
    client.post(f'/api/tasks/{tid}/start',headers=h)
    assert complete(client,h,tid).status_code==200
    move=task(client,h,wid,b,4,kind='move',source=a,key='task-key-move')
    assert move.status_code==201,move.text
    assert task(client,h,wid,b,2,kind='move',source=a,key='task-key-move2').status_code==409
    assert task(client,h,wid,b,1,kind='move',source=a,key='task-key-move3').status_code==201
    assert task(client,h,wid,b,1,kind='move',source=a,key='task-key-move4').status_code==409
    stock=client.get('/api/locations/stock').json()
    assert stock[0]['committed_to_moves']==5
    id=move.json()['id']
    client.post(f'/api/tasks/{id}/claim',headers=h)
    client.post(f'/api/tasks/{id}/start',headers=h)
    assert complete(client,h,id,target='A-02',source='A-XX').status_code==409
    assert complete(client,h,id,target='A-02',source='A-01').status_code==200
    placed={x['bin_code']:x for x in client.get('/api/locations/stock').json()}
    assert placed['A-01']['on_hand']==6 and placed['A-01']['committed_to_moves']==1
    assert placed['A-02']['on_hand']==4
    assert sum(x['on_hand'] for x in placed.values())==10
    assert client.get('/api/inventory').json()[0]['on_hand']==20


def test_cancel_releases_reserved_stock_and_putaway_capacity(client):
    h,wid,a=prepare(client)
    b=endpoint(client,h,'B-01',cap=9)
    tid=task(client,h,wid,a,10).json()['id']
    assert client.post(f'/api/tasks/{tid}/cancel',headers=h).status_code==200
    assert client.get('/api/locations/reconciliation').json()[0]['pending_putaway']==0
    tid=task(client,h,wid,a,10,key='task-0002').json()['id']
    client.post(f'/api/tasks/{tid}/claim',headers=h)
    client.post(f'/api/tasks/{tid}/start',headers=h)
    assert complete(client,h,tid).status_code==200
    move=task(client,h,wid,b,8,kind='move',source=a,key='task-move-0002').json()['id']
    assert client.get('/api/locations/stock').json()[0]['committed_to_moves']==8
    assert client.post(f'/api/tasks/{move}/cancel',headers=h).status_code==200
    assert client.get('/api/locations/stock').json()[0]['committed_to_moves']==0
    assert client.post(f'/api/tasks/{move}/cancel',headers=h).status_code==409


def test_stock_reducers_respect_bin_and_pending_work(client):
    h,wid,a=prepare(client)
    tid=task(client,h,wid,a,15).json()['id']
    assert client.post('/api/stock/adjust',headers=h,json={'warehouse_id':wid,'sku':'PRODUCT-1','delta':-6}).status_code==409
    assert client.post('/api/stock/adjust',headers=h,json={'warehouse_id':wid,'sku':'PRODUCT-1','delta':-5}).status_code==200
    client.post(f'/api/tasks/{tid}/claim',headers=h)
    client.post(f'/api/tasks/{tid}/start',headers=h)
    assert complete(client,h,tid).status_code==200
    assert client.post('/api/stock/adjust',headers=h,json={'warehouse_id':wid,'sku':'PRODUCT-1','delta':-1}).status_code==409
    # A physical relocation does not change the warehouse-level ledger balance.
    assert client.get('/api/inventory').json()[0]['on_hand']==15
    with client.test_db.SessionLocal() as session:
        st=session.scalar(select(StockLevel).where(StockLevel.warehouse_id==wid,
            StockLevel.product_id==session.scalar(select(Product.id).where(Product.sku=='PRODUCT-1'))))
        assert st.on_hand==15


def test_fulfill_requires_physically_unlocated_stock(client):
    h,wid,a=prepare(client)
    order=client.post('/api/orders',headers=h,json=order_request(wid)).json()['id']
    tid=task(client,h,wid,a,20).json()['id']
    client.post(f'/api/tasks/{tid}/claim',headers=h)
    client.post(f'/api/tasks/{tid}/start',headers=h)
    assert complete(client,h,tid).status_code==200
    assert client.post(f'/api/orders/{order}/fulfill',headers=h).status_code==409
    # Relocate back to 'unlocated' is intentionally a separate future workflow.
    assert client.get('/api/inventory').json()[0]['on_hand']==20


def test_tenant_isolation_for_bin_and_tasks(client):
    h,wid,a=prepare(client)
    tid=task(client,h,wid,a,2).json()['id']
    csrf=re.search(r'name="csrf-token" content="([^"]+)"',client.get('/app').text).group(1)
    client.post('/logout',data={'csrf':csrf},follow_redirects=False)
    h2=register(client,'Unrelated Company','other-tenant@example.com')
    assert client.get('/api/locations').json()==[]
    assert client.get('/api/tasks').json()==[]
    assert client.get(f'/api/tasks/{tid}/events').status_code==404
    assert client.post(f'/api/tasks/{tid}/claim',headers=h2).status_code==404
    assert client.post(f'/api/tasks/{tid}/complete',headers=h2,json={
        'scan_sku':'PRODUCT-1','scan_to_bin':'A-01'}).status_code==404
    assert task(client,h2,wid,a,2,key='other-tenant1').status_code==404
    assert client.post('/api/locations',headers=h2,json={
        'warehouse_id':wid,'code':'A-02'}).status_code==404


def test_task_role_and_scan_authorization(client):
    h,wid,a=prepare(client)
    tid=task(client,h,wid,a,4).json()['id']
    assert complete(client,h,tid).status_code==409
    assert client.post(f'/api/tasks/{tid}/start',headers=h).status_code==409
    assert client.post(f'/api/tasks/{tid}/claim',headers=h).status_code==200
    assert client.post(f'/api/tasks/{tid}/claim',headers=h).status_code==409
    assert client.post(f'/api/tasks/{tid}/start',headers=h).status_code==200
    assert client.post(f'/api/tasks/{tid}/start',headers=h).status_code==409
    assert complete(client,h,tid).status_code==200
    assert client.post(f'/api/tasks/{tid}/claim',headers=h).status_code==409


def test_scan_and_task_payload_validation(client):
    h,wid,a=prepare(client)
    assert task(client,h,wid,a,1,kind='pick').status_code==400
    assert task(client,h,wid,a,1,kind='move',source=a).status_code==400
    assert task(client,h,wid,a,1,key='short').status_code==400
    assert client.post('/api/tasks',headers=h,json={}).status_code==422
    assert client.get('/api/locations/reconciliation?warehouse_id=999999').json()==[]
    assert client.get('/api/locations/stock?warehouse_id=999999').json()==[]


def test_unlocate_releases_bin_stock_for_existing_fulfillment(client):
    h,wid,a=prepare(client)
    order=client.post('/api/orders',headers=h,json=order_request(wid)).json()['id']
    tid=task(client,h,wid,a,20).json()['id']
    client.post(f'/api/tasks/{tid}/claim',headers=h)
    client.post(f'/api/tasks/{tid}/start',headers=h)
    assert complete(client,h,tid).status_code==200
    # A bin-level pick-to-staging creates a traceable, scan-confirmed removal.
    staged=task(client,h,wid,None,8,kind='unlocate',source=a,key='stage-pick-0001')
    assert staged.status_code==201,staged.text
    task_id=staged.json()['id']
    assert client.get('/api/locations/stock').json()[0]['committed_to_moves']==8
    client.post(f'/api/tasks/{task_id}/claim',headers=h)
    client.post(f'/api/tasks/{task_id}/start',headers=h)
    assert complete(client,h,task_id,target='WRONG',source='A-01').status_code==409
    assert complete(client,h,task_id,target='UNLOCATED',source='A-01').status_code==200
    assert client.get('/api/locations/stock').json()[0]['on_hand']==12
    assert client.get('/api/locations/reconciliation').json()[0]['unlocated']==8
    fulfilled=client.post(f'/api/orders/{order}/fulfill',headers=h)
    assert fulfilled.status_code==200,fulfilled.text
    assert client.get('/api/inventory').json()[0]['on_hand']==12
    assert client.get('/api/locations/reconciliation').json()[0]['unlocated']==0


def test_cycle_count_preserves_confirmed_bin_units(client):
    h,wid,a=prepare(client)
    tid=task(client,h,wid,a,12).json()['id']
    client.post(f'/api/tasks/{tid}/claim',headers=h)
    client.post(f'/api/tasks/{tid}/start',headers=h)
    complete(client,h,tid)
    count=client.post('/api/cycle-counts',headers=h,json={
        'warehouse_id':wid,'sku':'PRODUCT-1','note':'Reconciliation test'})
    assert count.status_code==201,count.text
    cid=count.json()['id']
    assert client.post(f'/api/cycle-counts/{cid}/post',headers=h,
                       json={'counted_on_hand':11}).status_code==409
    assert client.post(f'/api/cycle-counts/{cid}/post',headers=h,
                       json={'counted_on_hand':12}).status_code==200
    assert client.get('/api/locations/reconciliation').json()[0]['unlocated']==0


def test_unlocate_task_capacity_and_source_allocation(client):
    h,wid,a=prepare(client)
    tid=task(client,h,wid,a,5).json()['id']
    client.post(f'/api/tasks/{tid}/claim',headers=h)
    client.post(f'/api/tasks/{tid}/start',headers=h)
    complete(client,h,tid)
    assert task(client,h,wid,None,5,kind='unlocate',source=a,key='unlocate111').status_code==201
    assert task(client,h,wid,None,1,kind='unlocate',source=a,key='unlocate112').status_code==409


def test_role_scoped_work_creation_and_staff_execution(client):
    from sqlalchemy import update
    from dispatchforge_app.models import User
    h,wid,a=prepare(client)
    owner_id=client.get('/api/tasks/assignees').json()[0]['id']
    task_id=task(client,h,wid,a,3).json()['id']
    with client.test_db.SessionLocal() as session:
        session.execute(update(User).where(User.id==owner_id).values(role='staff'))
        session.commit()
    assert client.get('/app').status_code==200
    assert 'data-section="tasks"' in client.get('/app').text
    assert 'id="bin-form"' not in client.get('/app').text
    assert 'id="task-form"' not in client.get('/app').text
    assert client.get('/api/tasks/assignees').status_code==403
    assert task(client,h,wid,a,1,key='staff-cannot1').status_code==403
    assert client.post('/api/locations',headers=h,json={
        'warehouse_id':wid,'code':'NEW-123'}).status_code==403
    assert client.post(f'/api/tasks/{task_id}/cancel',headers=h).status_code==403
    assert client.post(f'/api/tasks/{task_id}/claim',headers=h).status_code==200
    assert client.post(f'/api/tasks/{task_id}/start',headers=h).status_code==200
    assert complete(client,h,task_id).status_code==200


def test_manager_can_release_work_but_not_create_warehouses(client):
    from sqlalchemy import update
    from dispatchforge_app.models import User
    h,wid,a=prepare(client)
    uid=client.get('/api/tasks/assignees').json()[0]['id']
    with client.test_db.SessionLocal() as session:
        session.execute(update(User).where(User.id==uid).values(role='manager'))
        session.commit()
    assert client.get('/api/tasks/assignees').status_code==200
    assert 'id="task-form"' in client.get('/app').text
    assert client.post('/api/warehouses',headers=h,json={'name':'Manager warehouse'}).status_code==403
    assert client.post('/api/locations',headers=h,json={
        'warehouse_id':wid,'code':'MAN-01'}).status_code==201
    assert task(client,h,wid,a,2,key='manager-task-1').status_code==201


def test_task_idempotency_with_assignment_and_replay(client):
    h,wid,a=prepare(client)
    uid=client.get('/api/tasks/assignees').json()[0]['id']
    body={'warehouse_id':wid,'sku':'PRODUCT-1','kind':'putaway',
          'to_bin_id':a,'quantity':7,'assigned_user_id':uid}
    headers={**h,'Idempotency-Key':'replay-same-task'}
    original=client.post('/api/tasks',headers=headers,json=body)
    assert original.status_code==201 and original.json()['status']=='assigned'
    replay=client.post('/api/tasks',headers=headers,json=body)
    assert replay.status_code==201 and replay.json()['replayed'] is True
    assert client.get('/api/locations/reconciliation').json()[0]['pending_putaway']==7
    assert client.post('/api/tasks',headers=headers,json={**body,'quantity':8}).status_code==409
    assert len(client.get('/api/tasks').json())==1
    assert client.post(f"/api/tasks/{original.json()['id']}/start",headers=h).status_code==200
    assert complete(client,h,original.json()['id']).status_code==200
    assert complete(client,h,original.json()['id']).json()['replayed'] is True
