"""Bin/SKU cycle counting protects tenant inventory, work and audit history."""
import re
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from dispatchforge_app.database import Database
from dispatchforge_app.models import BinCycleCount, BinStock, StockLevel
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from tests_web.test_warehouse_web import register, add_stock, order_request
from tests_web.test_warehouse_execution import endpoint, task, complete


@pytest.fixture
def client(tmp_path):
    url = f"sqlite:///{tmp_path / 'bin-counts.sqlite3'}"
    db = Database(url)
    with TestClient(create_app(db, Settings('development', 'bin-count-secret', url))) as c:
        c.test_db = db
        yield c
    db.dispose()


def placed(client, h, qty=10, stock=20, cap=None):
    wid = add_stock(client, h, 'COUNT-1', stock)
    bid = endpoint(client, h, 'C-01', wid=wid, cap=cap)
    t = task(client, h, wid, bid, qty, sku='COUNT-1').json()['id']
    assert client.post(f'/api/tasks/{t}/claim', headers=h).status_code == 200
    assert client.post(f'/api/tasks/{t}/start', headers=h).status_code == 200
    assert complete(client, h, t, target='C-01', sku='COUNT-1').status_code == 200
    return wid, bid


def start(client, h, wid, bid, sku='COUNT-1'):
    return client.post('/api/bin-cycle-counts', headers=h, json={
        'warehouse_id':wid, 'bin_id':bid, 'sku':sku, 'note':'Aisle supervisor physical tally'})


def post(client, h, cid, qty):
    return client.post(f'/api/bin-cycle-counts/{cid}/post', headers=h, json={
        'counted_on_hand':qty})


def test_positive_variance_updates_bin_and_aggregate_and_audit(client):
    h = register(client)
    wid, bid = placed(client, h, qty=10, stock=20)
    response = start(client, h, wid, bid)
    assert response.status_code == 201, response.text
    assert response.json()['expected_on_hand'] == 10
    cid = response.json()['id']
    assert start(client, h, wid, bid).status_code == 409
    posted = post(client, h, cid, 13)
    assert posted.status_code == 200, posted.text
    assert posted.json()['variance'] == 3
    stock = client.get('/api/inventory').json()[0]
    bins = client.get('/api/locations/stock').json()
    summary = client.get('/api/locations/reconciliation').json()[0]
    assert stock['on_hand'] == 23
    assert bins[0]['on_hand'] == 13
    assert (summary['on_hand'], summary['placed'], summary['unlocated']) == (23, 13, 10)
    assert client.get('/api/movements').json()[0]['kind'] == 'bin_cycle_count'
    assert client.get('/api/movements').json()[0]['on_hand_delta'] == 3
    assert client.get('/api/bin-cycle-counts').json()[0]['status'] == 'posted'
    assert post(client, h, cid, 13).status_code == 409
    assert client.get('/api/inventory').json()[0]['on_hand'] == 23


def test_negative_variance_and_reservation_guard(client):
    h = register(client)
    wid, bid = placed(client, h, qty=12, stock=20)
    order = client.post('/api/orders', headers=h, json=order_request(
        wid, [{'sku':'COUNT-1','quantity':19}]))
    assert order.status_code == 201
    cid = start(client, h, wid, bid).json()['id']
    assert post(client, h, cid, 10).status_code == 409
    assert client.get('/api/bin-cycle-counts').json()[0]['status'] == 'open'
    assert client.get('/api/locations/stock').json()[0]['on_hand'] == 12
    assert client.post(f'/api/orders/{order.json()["id"]}/cancel', headers=h).status_code == 200
    assert post(client, h, cid, 10).status_code == 409  # Reservation history changed
    assert client.post(f'/api/bin-cycle-counts/{cid}/cancel', headers=h).status_code == 200
    cid = start(client, h, wid, bid).json()['id']
    posted = post(client, h, cid, 10)
    assert posted.status_code == 200, posted.text
    assert posted.json()['variance'] == -2
    assert client.get('/api/inventory').json()[0]['on_hand'] == 18
    assert client.get('/api/locations/stock').json()[0]['on_hand'] == 10


def test_stale_snapshot_cannot_overwrite_new_receipt(client):
    h = register(client)
    wid, bid = placed(client, h)
    cid = start(client, h, wid, bid).json()['id']
    receipt = client.post('/api/stock/receive', headers=h, json={
        'warehouse_id':wid, 'sku':'COUNT-1', 'quantity':2})
    assert receipt.status_code == 200
    assert post(client, h, cid, 8).status_code == 409
    assert client.get('/api/inventory').json()[0]['on_hand'] == 22
    assert client.get('/api/bin-cycle-counts').json()[0]['status'] == 'open'
    assert client.post(f'/api/bin-cycle-counts/{cid}/cancel', headers=h).status_code == 200
    fresh = start(client, h, wid, bid)
    assert fresh.status_code == 201
    assert post(client, h, fresh.json()['id'], 8).status_code == 200


def test_open_work_rejects_count_and_a_new_task_blocks_post(client):
    h = register(client)
    wid, bid = placed(client, h)
    other = endpoint(client, h, 'C-02', wid=wid)
    movement = task(client, h, wid, other, 3, kind='move', source=bid,
                    key='movement-count-0001', sku='COUNT-1')
    assert movement.status_code == 201, movement.text
    assert start(client, h, wid, bid).status_code == 409
    assert client.post(f'/api/tasks/{movement.json()["id"]}/cancel', headers=h).status_code == 200
    cid = start(client, h, wid, bid).json()['id']
    movement2 = task(client, h, wid, other, 3, kind='move', source=bid,
                     key='movement-count-0002', sku='COUNT-1')
    assert movement2.status_code == 201
    assert post(client, h, cid, 9).status_code == 409
    assert client.post(f'/api/tasks/{movement2.json()["id"]}/cancel', headers=h).status_code == 200
    # Event watermark detects movement even when the bin quantity returned to 10.
    assert post(client, h, cid, 9).status_code == 409
    assert client.post(f'/api/bin-cycle-counts/{cid}/cancel', headers=h).status_code == 200
    cid = start(client, h, wid, bid).json()['id']
    assert post(client, h, cid, 9).status_code == 200


def test_bin_capacity_includes_other_stock_and_pending_inbound(client):
    h = register(client)
    wid, bid = placed(client, h, qty=9, stock=20, cap=10)
    cid = start(client, h, wid, bid).json()['id']
    assert post(client, h, cid, 11).status_code == 409
    assert client.get('/api/inventory').json()[0]['on_hand'] == 20
    assert client.get('/api/locations/stock').json()[0]['on_hand'] == 9
    assert post(client, h, cid, 10).status_code == 200


def test_count_finds_stock_in_an_empty_bin(client):
    h = register(client)
    wid = add_stock(client, h, 'COUNT-1', 20)
    bid = endpoint(client, h, 'EMPTY-01', wid=wid, cap=25)
    cid = start(client, h, wid, bid).json()['id']
    assert post(client, h, cid, 5).status_code == 200
    summary = client.get('/api/locations/reconciliation').json()[0]
    assert (summary['on_hand'],summary['placed'],summary['unlocated']) == (25,5,20)
    assert client.get('/api/locations/stock').json()[0]['on_hand'] == 5


def test_zero_variance_is_audited_without_stock_change(client):
    h = register(client)
    wid, bid = placed(client, h)
    cid = start(client, h, wid, bid).json()['id']
    assert post(client, h, cid, 10).status_code == 200
    assert client.get('/api/inventory').json()[0]['on_hand'] == 20
    assert client.get('/api/movements').json()[0]['on_hand_delta'] == 0
    assert client.get('/api/bin-cycle-counts').json()[0]['variance'] == 0


def test_count_requires_valid_bin_workspace_and_csrf(client):
    h = register(client)
    wid, bid = placed(client, h)
    assert client.post('/api/bin-cycle-counts', json={
        'warehouse_id':wid,'bin_id':bid,'sku':'COUNT-1'}).status_code == 403
    assert start(client, h, wid+1234, bid).status_code == 404
    assert start(client, h, wid, bid+1234).status_code == 404
    assert start(client, h, wid, bid, sku='WRONG').status_code in (400,404)
    cid = start(client, h, wid, bid).json()['id']
    token = re.search(r'name="csrf-token" content="([^"]+)"', client.get('/app').text).group(1)
    client.post('/logout', data={'csrf':token}, follow_redirects=False)
    other_h = register(client, 'Another Warehouse', 'another@example.com')
    assert client.get('/api/bin-cycle-counts').json() == []
    assert post(client, other_h, cid, 15).status_code == 404
    assert client.post(f'/api/bin-cycle-counts/{cid}/cancel', headers=other_h).status_code == 404
    assert start(client, other_h, wid, bid).status_code == 404


def test_cancel_is_terminal_and_validation_requires_positive_ids(client):
    h = register(client)
    wid, bid = placed(client, h)
    assert start(client, h, wid, -1).status_code == 422
    cid = start(client, h, wid, bid).json()['id']
    response = client.post(f'/api/bin-cycle-counts/{cid}/cancel', headers=h)
    assert response.status_code == 200
    assert response.json()['status'] == 'canceled'
    assert post(client, h, cid, 5).status_code == 409
    assert client.post(f'/api/bin-cycle-counts/{cid}/cancel', headers=h).status_code == 409
    assert client.get('/api/inventory').json()[0]['on_hand'] == 20
    assert client.get('/api/locations/stock').json()[0]['on_hand'] == 10


def test_demo_counts_read_only(client):
    assert client.get('/api/bin-cycle-counts?demo=true').status_code == 200
    assert client.post('/api/bin-cycle-counts', json={
        'warehouse_id':1,'bin_id':1,'sku':'SAMPLE'}).status_code == 401


def test_invariants_at_database_level(client):
    h = register(client)
    wid, bid = placed(client, h)
    cid = start(client, h, wid, bid).json()['id']
    assert post(client, h, cid, 7).status_code == 200
    with client.test_db.SessionLocal() as s:
        count = s.get(BinCycleCount, cid)
        bs = s.scalar(select(BinStock).where(BinStock.bin_id == bid))
        aggregate = s.scalar(select(StockLevel).where(StockLevel.warehouse_id == wid))
        assert count.posted_by is not None
        assert count.created_by is not None
        assert count.expected_warehouse_on_hand == 20
        assert bs.on_hand == 7 and bs.allocated == 0
        assert aggregate.on_hand == 17


def test_staff_can_start_but_only_owner_can_post_or_cancel(client):
    owner = register(client)
    wid, bid = placed(client, owner)
    token = client.post('/api/staff/invitations', headers=owner,
                        json={'email':'counter@example.com','role':'staff'}).json()['token']
    response = client.post('/api/staff/invitations/accept', json={
        'token':token,'password':'counter-password-123'})
    assert response.status_code == 201
    slug = client.get('/app').text.split('class="slug-code">')[1].split('</code>')[0]
    csrf = re.search(r'name="csrf-token" content="([^"]+)"', client.get('/app').text).group(1)
    client.post('/logout', data={'csrf':csrf}, follow_redirects=False)
    login_csrf = re.search(r'name="csrf" value="([^"]+)"', client.get('/login').text).group(1)
    assert client.post('/login', data={'csrf':login_csrf, 'workspace':slug,
        'email':'counter@example.com', 'password':'counter-password-123'},
        follow_redirects=False).status_code == 303
    staff = {'X-CSRF-Token':re.search(r'name="csrf-token" content="([^"]+)"',
                                    client.get('/app').text).group(1)}
    count = start(client, staff, wid, bid)
    assert count.status_code == 201
    cid = count.json()['id']
    assert post(client, staff, cid, 9).status_code == 403
    assert client.post(f'/api/bin-cycle-counts/{cid}/cancel', headers=staff).status_code == 403
    assert client.get('/api/bin-cycle-counts').json()[0]['status'] == 'open'


def test_dashboard_exposes_bin_count_workbench(client):
    h = register(client)
    html = client.get('/app').text
    assert 'id="bin-count-form"' in html
    assert 'id="bin-counts-table"' in html
    assert 'Count an individual storage bin' in html
    demo = client.get('/demo').text
    assert 'id="bin-count-form"' not in demo
    assert 'id="bin-counts-table"' in demo
