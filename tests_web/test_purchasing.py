"""Purchasing workflow tests: tenants, partial receipt, audit trail and input validation."""
import re
import pytest
from fastapi.testclient import TestClient
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app


@pytest.fixture
def client(tmp_path):
    url = f"sqlite:///{tmp_path / 'purchasing.sqlite3'}"
    db = Database(url)
    with TestClient(create_app(db, Settings('development', 'integration-test-secret', url))) as c:
        yield c
    db.dispose()


def register(c, business='Denton Supply', email='denton@example.com'):
    page = c.get('/register').text
    csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
    response = c.post('/register', data={
        'csrf': csrf, 'business_name': business, 'email': email,
        'password': 'long-enough-password-for-tests'
    }, follow_redirects=False)
    assert response.status_code == 303, response.text
    csrf = re.search(r'name="csrf-token" content="([^"]+)"', c.get('/app').text).group(1)
    return {'X-CSRF-Token': csrf}


def setup(c, headers):
    warehouse = c.get('/api/warehouses').json()[0]['id']
    assert c.post('/api/products', headers=headers, json={
        'sku': 'WIDGET', 'name': 'Warehouse widget'}).status_code == 201
    s = c.post('/api/suppliers', headers=headers, json={'name': 'Parts Distributor'})
    assert s.status_code == 201, s.text
    return warehouse, s.json()['id']


def create(c, headers, warehouse, supplier, items=None, reference='PO-100'):
    return c.post('/api/purchase-orders', headers=headers, json={
        'warehouse_id': warehouse, 'supplier_id': supplier,
        'reference': reference, 'expected_date': '2026-12-20',
        'items': items or [{'sku': 'WIDGET', 'quantity': 12}]
    })


def test_purchase_order_receiving_updates_inventory_and_history(client):
    h = register(client)
    w, s = setup(client, h)
    p = create(client, h, w, s)
    assert p.status_code == 201, p.text
    order_id = p.json()['id']
    po = client.get('/api/purchase-orders').json()[0]
    assert (po['reference'], po['status'], po['items'][0]['outstanding']) == ('PO-100', 'ordered', 12)
    assert client.get('/api/inventory').json()[0]['on_hand'] == 0
    line_id = po['items'][0]['line_id']
    receive = client.post(f'/api/purchase-orders/{order_id}/receive', headers=h,
                          json={'line_id': line_id, 'quantity': 5})
    assert receive.status_code == 200 and receive.json()['status'] == 'partial'
    assert client.get('/api/inventory').json()[0]['on_hand'] == 5
    assert client.get('/api/purchase-orders').json()[0]['items'][0]['outstanding'] == 7
    finish = client.post(f'/api/purchase-orders/{order_id}/receive', headers=h,
                         json={'line_id': line_id, 'quantity': 7})
    assert finish.json()['status'] == 'received'
    assert client.get('/api/inventory').json()[0]['on_hand'] == 12
    movements = client.get('/api/movements').json()
    assert sum(m['on_hand_delta'] for m in movements if m['kind'] == 'purchase_receipt') == 12
    assert client.post(f'/api/purchase-orders/{order_id}/receive', headers=h,
                       json={'line_id': line_id, 'quantity': 1}).status_code == 409


def test_over_receive_is_rejected_atomically(client):
    h = register(client)
    w, s = setup(client, h)
    order_id = create(client, h, w, s).json()['id']
    line = client.get('/api/purchase-orders').json()[0]['items'][0]['line_id']
    bad = client.post(f'/api/purchase-orders/{order_id}/receive', headers=h,
                      json={'line_id': line, 'quantity': 13})
    assert bad.status_code == 409
    assert client.get('/api/inventory').json()[0]['on_hand'] == 0
    assert client.get('/api/purchase-orders').json()[0]['items'][0]['received'] == 0
    assert client.get('/api/movements').json() == []


def test_cancel_after_partial_receipt_keeps_received_goods(client):
    h = register(client)
    w, s = setup(client, h)
    order_id = create(client, h, w, s).json()['id']
    line = client.get('/api/purchase-orders').json()[0]['items'][0]['line_id']
    client.post(f'/api/purchase-orders/{order_id}/receive', headers=h,
                json={'line_id': line, 'quantity': 4})
    assert client.post(f'/api/purchase-orders/{order_id}/cancel', headers=h).json()['status'] == 'cancelled'
    assert client.get('/api/inventory').json()[0]['on_hand'] == 4
    assert client.post(f'/api/purchase-orders/{order_id}/receive', headers=h,
                       json={'line_id': line, 'quantity': 1}).status_code == 409
    assert client.post(f'/api/purchase-orders/{order_id}/cancel', headers=h).status_code == 409


def test_reject_unknown_supplier_warehouse_duplicate_ref_and_duplicate_sku(client):
    h = register(client)
    w, s = setup(client, h)
    assert create(client, h, w, 9999).status_code == 404
    assert create(client, h, 9999, s).status_code == 404
    assert create(client, h, w, s).status_code == 201
    assert create(client, h, w, s).status_code == 409
    repeat = create(client, h, w, s,
                    [{'sku': 'WIDGET', 'quantity': 1}, {'sku': 'WIDGET', 'quantity': 2}],
                    reference='PO-101')
    assert repeat.status_code == 400
    assert len(client.get('/api/purchase-orders').json()) == 1


def test_multi_item_purchase_remains_partial_until_all_received(client):
    h = register(client)
    w, s = setup(client, h)
    assert client.post('/api/products', headers=h,
                       json={'sku': 'TAPE', 'name': 'Packaging tape'}).status_code == 201
    r = create(client, h, w, s, [{'sku': 'WIDGET', 'quantity': 2}, {'sku': 'TAPE', 'quantity': 3}])
    assert r.status_code == 201, r.text
    po = client.get('/api/purchase-orders').json()[0]
    a, b = po['items']
    assert client.post(f'/api/purchase-orders/{po["id"]}/receive', headers=h,
                       json={'line_id': a['line_id'], 'quantity': 2}).json()['status'] == 'partial'
    assert client.post(f'/api/purchase-orders/{po["id"]}/receive', headers=h,
                       json={'line_id': b['line_id'], 'quantity': 3}).json()['status'] == 'received'
    assert sum(row['on_hand'] for row in client.get('/api/inventory').json()) == 5


def test_demo_purchase_orders_read_only_and_csrf_required(client):
    assert client.get('/api/purchase-orders?demo=true').status_code == 200
    assert client.get('/api/purchase-orders').status_code == 401
    assert client.post('/api/purchase-orders', json={'warehouse_id': 1, 'supplier_id': 1,
        'reference': 'PO-UNAUTH', 'items': [{'sku': 'WIDGET', 'quantity': 1}]}).status_code == 401
    h = register(client)
    w, s = setup(client, h)
    json = {'warehouse_id': w, 'supplier_id': s,
            'reference': 'PO-CSRF', 'items': [{'sku': 'WIDGET', 'quantity': 2}]}
    assert client.post('/api/purchase-orders', json=json).status_code == 403
    assert client.post('/api/purchase-orders', headers={'X-CSRF-Token': 'wrong'},
                       json=json).status_code == 403
    assert client.post('/api/purchase-orders', headers=h, json=json).status_code == 201


def test_purchasing_tenant_isolation(client):
    h_a = register(client, 'Company A', 'a@example.com')
    w_a, s_a = setup(client, h_a)
    order = create(client, h_a, w_a, s_a).json()['id']
    line = client.get('/api/purchase-orders').json()[0]['items'][0]['line_id']
    token = re.search(r'name="csrf-token" content="([^"]+)"', client.get('/app').text).group(1)
    client.post('/logout', data={'csrf': token}, follow_redirects=False)
    h_b = register(client, 'Company B', 'b@example.com')
    w_b, s_b = setup(client, h_b)
    assert client.get('/api/purchase-orders').json() == []
    assert create(client, h_b, w_b, s_a).status_code == 404
    assert create(client, h_b, w_a, s_b).status_code == 404
    assert client.post(f'/api/purchase-orders/{order}/receive', headers=h_b,
                       json={'line_id': line, 'quantity': 1}).status_code == 404
    assert client.post(f'/api/purchase-orders/{order}/cancel', headers=h_b).status_code == 404
    assert client.get('/api/inventory').json()[0]['on_hand'] == 0


def test_purchase_input_validation(client):
    h = register(client)
    w, s = setup(client, h)
    assert create(client, h, w, s, [{'sku': 'MISSING', 'quantity': 1}]).status_code == 404
    assert create(client, h, w, s, [{'sku': 'WIDGET', 'quantity': 0}]).status_code == 422
    assert create(client, h, w, s, [{'sku': 'WIDGET', 'quantity': 1}], reference='  ').status_code == 400
    assert client.get('/api/purchase-orders').json() == []


def test_elveriq_public_brand_and_purchasing_demo(client):
    homepage = client.get('/').text
    demo = client.get('/demo').text
    assert 'Elveriq' in homepage
    assert 'Elveriq' in demo
    assert 'Purchasing &amp; receiving' in demo
    assert 'DispatchForge' not in homepage
    assert client.get('/api/health').json()['app'] == 'elveriq'
    purchases = client.get('/api/purchase-orders?demo=true').json()
    assert len(purchases) == 1
    assert purchases[0]['reference'] == 'SAMPLE-PO-001'


def test_purchase_receipt_requires_csrf(client):
    h = register(client)
    w, s = setup(client, h)
    po_id = create(client, h, w, s).json()['id']
    line_id = client.get('/api/purchase-orders').json()[0]['items'][0]['line_id']
    result = client.post(f'/api/purchase-orders/{po_id}/receive',
                         json={'line_id': line_id, 'quantity': 1})
    assert result.status_code == 403
    assert client.get('/api/inventory').json()[0]['on_hand'] == 0
