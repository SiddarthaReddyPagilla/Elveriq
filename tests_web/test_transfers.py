"""Transfer tests cover stock integrity, roles, audit trails and tenant boundaries."""
import pytest
from uuid import uuid4
from sqlalchemy import event, select
from dispatchforge_app.models import StockLevel, StockMovement, InventoryTransfer
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
        c.test_db = db
        yield c
    db.dispose()


def setup(c):
    h = register(c)
    a = add_stock(c, h, "WATER", 20)
    b = c.post('/api/warehouses', headers=h, json={'name': 'Second Warehouse'}).json()['id']
    return h, a, b


def transfer(c, h, a, b, qty=5, key=None, sku='WATER', note='Scheduled move'):
    return c.post('/api/transfers', headers={**h, 'Idempotency-Key': key or str(uuid4())}, json={
        'source_warehouse_id': a, 'destination_warehouse_id': b,
        'sku': sku, 'quantity': qty, 'note': note})


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
    assert client.post('/api/transfers',headers={'Idempotency-Key': str(uuid4())},json={'source_warehouse_id':a,
        'destination_warehouse_id':b,'sku':'WATER','quantity':1}).status_code == 403


def test_transfer_audit_has_shared_structured_id(client):
    h, a, b = setup(client)
    result = transfer(client, h, a, b)
    assert result.status_code == 201, result.text
    ident = result.json()['id']
    movements = [m for m in client.get('/api/movements').json()
                 if m['kind'].startswith('transfer_')]
    assert len(movements) == 2
    assert {m['transfer_id'] for m in movements} == {ident}
    assert sum(m['on_hand_delta'] for m in movements) == 0
    assert {m['on_hand_delta'] for m in movements} == {-5, 5}


def test_replay_of_identical_request_does_not_move_stock_twice(client):
    h, a, b = setup(client)
    key = str(uuid4())
    first = transfer(client, h, a, b, qty=7, key=key)
    second = transfer(client, h, a, b, qty=7, key=key)
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert first.json()['id'] == second.json()['id']
    assert second.json()['replayed'] is True
    inv = {r['warehouse_id']: r['on_hand'] for r in client.get('/api/inventory').json()}
    assert inv == {a: 13, b: 7}
    assert len(client.get('/api/transfers').json()) == 1
    assert len([m for m in client.get('/api/movements').json()
                if m['kind'].startswith('transfer_')]) == 2


def test_reused_key_with_changed_request_is_conflict(client):
    h, a, b = setup(client)
    key = str(uuid4())
    assert transfer(client, h, a, b, qty=5, key=key).status_code == 201
    changed = transfer(client, h, a, b, qty=6, key=key)
    assert changed.status_code == 409, changed.text
    # A note change also means a different request.
    assert transfer(client, h, a, b, qty=5, key=key, note='other').status_code == 409
    assert {r['warehouse_id']: r['on_hand'] for r in client.get('/api/inventory').json()} == {a: 15, b: 5}
    assert len(client.get('/api/transfers').json()) == 1


def test_debit_rolls_back_if_destination_update_fails(client):
    h, a, b = setup(client)
    attempts = {'n': 0}

    def break_second_stock_write(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().lower().startswith('update stock_levels'):
            attempts['n'] += 1
            if attempts['n'] == 2:
                raise RuntimeError('Injected destination write failure')

    engine = client.test_db.engine
    event.listen(engine, 'before_cursor_execute', break_second_stock_write)
    try:
        with pytest.raises(RuntimeError, match='Injected destination'):
            transfer(client, h, a, b, key=str(uuid4()))
    finally:
        event.remove(engine, 'before_cursor_execute', break_second_stock_write)

    assert attempts['n'] == 2
    assert {r['warehouse_id']: r['on_hand'] for r in client.get('/api/inventory').json()} == {a: 20, b: 0}
    assert client.get('/api/transfers').json() == []
    assert all(not m['kind'].startswith('transfer_') for m in client.get('/api/movements').json())


def test_missing_idempotency_key_is_rejected(client):
    h, a, b = setup(client)
    response = client.post('/api/transfers', headers=h, json={
        'source_warehouse_id': a, 'destination_warehouse_id': b,
        'sku': 'WATER', 'quantity': 1,
    })
    assert response.status_code == 422
    assert client.get('/api/transfers').json() == []


def test_warehouse_authorization_on_either_side_and_disabled_actor(client):
    h, source, dest = setup(client)
    # Create a second tenant and capture its warehouse ID.
    import re
    csrf = re.search(r'name="csrf-token" content="([^"]+)"', client.get('/app').text).group(1)
    assert client.post('/logout', data={'csrf': csrf}, follow_redirects=False).status_code == 303
    other = register(client, 'Other Tenant', 'other-operator@example.com')
    foreign = client.get('/api/warehouses').json()[0]['id']
    assert client.post('/api/products', headers=other,
                       json={'sku': 'WATER', 'name': 'Water'}).status_code == 201
    # Both source and destination ownership must be checked.
    assert transfer(client, other, source, foreign, key=str(uuid4())).status_code == 404
    assert transfer(client, other, foreign, dest, key=str(uuid4())).status_code == 404
    assert client.get('/api/transfers').json() == []
    assert all(not m['kind'].startswith('transfer_') for m in client.get('/api/movements').json())
    # Disabled account must not be able to create a transfer.
    with client.test_db.SessionLocal() as session:
        from dispatchforge_app.models import User
        from sqlalchemy import update
        session.execute(update(User).where(User.email == 'other-operator@example.com').values(role='disabled'))
        session.commit()
    assert transfer(client, other, foreign, foreign + 1000, key=str(uuid4())).status_code == 401


def test_transfer_key_is_scoped_per_business(client):
    h, a, b = setup(client)
    same_key = str(uuid4())
    assert transfer(client, h, a, b, key=same_key).status_code == 201
    import re
    csrf = re.search(r'name="csrf-token" content="([^"]+)"', client.get('/app').text).group(1)
    client.post('/logout', data={'csrf': csrf}, follow_redirects=False)
    other = register(client, 'Second Tenant', 'second-operator@example.com')
    a2 = add_stock(client, other, 'WATER', 20)
    b2 = client.post('/api/warehouses', headers=other,
        json={'name': 'East Warehouse'}).json()['id']
    second = transfer(client, other, a2, b2, key=same_key)
    assert second.status_code == 201, second.text
    assert second.json()['replayed'] is False
