"""End-to-end checks for website, REST API, tenant isolation, and inventory integrity."""
from datetime import date, timedelta
import io
import re
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from dispatchforge_app.auth import hash_password, verify_password
from dispatchforge_app.database import Database
from dispatchforge_app.models import Business
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app


@pytest.fixture
def client(tmp_path):
    url = f"sqlite:///{tmp_path / 'warehouse.sqlite3'}"
    db = Database(url)
    app = create_app(db, Settings("development", "local-test-secret", url))
    with TestClient(app) as client:
        client.test_db = db
        yield client
    db.dispose()


def csrf(client, page="/register"):
    html = client.get(page).text
    match = (re.search(r'name="csrf" value="([^"]+)"', html)
             or re.search(r'name="csrf-token" content="([^"]+)"', html))
    assert match, "CSRF token is missing from page"
    return match.group(1)


def register(client, name="Denton Supplies", email="owner@example.com"):
    token = csrf(client)
    response = client.post("/register", data={"csrf": token, "business_name": name,
                 "email": email, "password": "correct-horse-battery-staple"}, follow_redirects=False)
    assert response.status_code == 303
    html = client.get("/app").text
    token = re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)
    return {"X-CSRF-Token": token}


def add_stock(client, headers, sku="PRODUCT-1", quantity=20):
    warehouse_id = client.get("/api/warehouses").json()[0]["id"]
    created = client.post("/api/products", headers=headers,
        json={"sku": sku, "name": "Sample Product", "reorder_point": 5})
    assert created.status_code == 201, created.text
    received = client.post("/api/stock/receive", headers=headers,
        json={"sku": sku, "quantity": quantity, "warehouse_id": warehouse_id})
    assert received.status_code == 200, received.text
    return warehouse_id


def order_request(warehouse_id, items=None):
    return {"warehouse_id": warehouse_id, "customer_name": "Example Buyer",
            "due_date": (date.today() + timedelta(days=2)).isoformat(),
            "items": items or [{"sku": "PRODUCT-1", "quantity": 8}]}


def test_public_demo_is_visible_but_cannot_mutate(client):
    assert client.get("/").status_code == 200
    assert client.get("/demo").status_code == 200
    overview = client.get("/api/overview?demo=true").json()
    assert overview["demo"] is True
    assert overview["products"] == 7
    assert overview["warehouses"] == 2
    assert client.get("/api/overview").status_code == 401
    assert client.post("/api/products", json={"sku": "X", "name": "X"}).status_code == 401
    assert client.get("/api/export/inventory.csv?demo=true").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"


def test_registration_and_login_are_workspace_scoped(client):
    headers = register(client)
    assert client.get("/app").status_code == 200
    with client.test_db.SessionLocal() as session:
        workspace = session.scalar(select(Business.slug).where(Business.name == "Denton Supplies"))
    assert workspace
    assert client.post("/logout", data={"csrf": csrf(client, "/app")}, follow_redirects=False).status_code == 303
    assert client.get("/app", follow_redirects=False).status_code == 303
    token = csrf(client, "/login")
    wrong = client.post("/login", data={"csrf": token, "workspace": "wrong-workspace",
                  "email": "owner@example.com", "password": "correct-horse-battery-staple"})
    assert wrong.status_code == 401
    valid = client.post("/login", data={"csrf": csrf(client, "/login"), "workspace": workspace,
                  "email": "owner@example.com", "password": "correct-horse-battery-staple"}, follow_redirects=False)
    assert valid.status_code == 303
    assert client.get("/api/overview").status_code == 200


def test_csrf_prevents_cross_site_writes(client):
    headers = register(client)
    assert client.post("/api/products", json={"sku": "ABC", "name": "ABC"}).status_code == 403
    assert client.post("/api/products", headers={"X-CSRF-Token": "wrong"},
                       json={"sku": "ABC", "name": "ABC"}).status_code == 403
    assert client.post("/api/products", headers=headers,
                       json={"sku": "ABC", "name": "ABC"}).status_code == 201
    assert len(client.get("/api/products").json()) == 1


def test_stock_receiving_and_audit_trail(client):
    headers = register(client)
    warehouse_id = add_stock(client, headers)
    inv = client.get("/api/inventory").json()[0]
    assert (inv["on_hand"], inv["reserved"], inv["available"]) == (20, 0, 20)
    movements = client.get("/api/movements").json()
    assert len(movements) == 1
    assert movements[0]["kind"] == "receive"
    assert movements[0]["on_hand_delta"] == 20
    assert client.post("/api/stock/adjust", headers=headers, json={
        "warehouse_id": warehouse_id, "sku": "PRODUCT-1", "delta": -25}).status_code == 409
    assert client.get("/api/inventory").json()[0]["on_hand"] == 20


def test_future_order_reserves_then_fulfills_once(client):
    headers = register(client)
    wid = add_stock(client, headers)
    result = client.post("/api/orders", headers=headers, json=order_request(wid))
    assert result.status_code == 201, result.text
    order_id = result.json()["id"]
    available = client.get("/api/inventory").json()[0]
    assert (available["on_hand"], available["reserved"], available["available"]) == (20, 8, 12)
    excessive = client.post("/api/orders", headers=headers,
                            json=order_request(wid, [{"sku": "PRODUCT-1", "quantity": 13}]))
    assert excessive.status_code == 409
    assert client.post(f"/api/orders/{order_id}/fulfill", headers=headers).status_code == 200
    assert client.post(f"/api/orders/{order_id}/fulfill", headers=headers).status_code == 409
    final = client.get("/api/inventory").json()[0]
    assert (final["on_hand"], final["reserved"], final["available"]) == (12, 0, 12)
    assert len(client.get("/api/orders").json()) == 1


def test_cancel_returns_reserved_units(client):
    headers = register(client)
    wid = add_stock(client, headers)
    order_id = client.post("/api/orders", headers=headers, json=order_request(wid)).json()["id"]
    assert client.post(f"/api/orders/{order_id}/cancel", headers=headers).status_code == 200
    assert client.get("/api/inventory").json()[0]["reserved"] == 0
    assert client.post(f"/api/orders/{order_id}/cancel", headers=headers).status_code == 409
    assert client.get("/api/inventory").json()[0]["on_hand"] == 20


def test_failed_multi_item_order_rolls_back_entire_reservation(client):
    headers = register(client)
    wid = add_stock(client, headers)
    request = order_request(wid, [{"sku": "PRODUCT-1", "quantity": 4},
                                  {"sku": "NOT-IN-STOCK", "quantity": 1}])
    result = client.post("/api/orders", headers=headers, json=request)
    assert result.status_code == 404
    assert client.get("/api/inventory").json()[0]["reserved"] == 0
    assert client.get("/api/orders").json() == []


def test_tenant_isolation_for_stock_order_and_warehouse_ids(tmp_path):
    url = f"sqlite:///{tmp_path / 'shared.sqlite3'}"
    db = Database(url)
    app = create_app(db, Settings("development", "different-test-secret", url))
    with TestClient(app) as a, TestClient(app) as b:
        ha = register(a, name="Warehouse A", email="a@example.com")
        wa = add_stock(a, ha, "SHARED-SKU", 31)
        hb = register(b, name="Warehouse B", email="b@example.com")
        wb = add_stock(b, hb, "OTHER-SKU", 12)
        assert wa != wb
        assert a.get("/api/products").json()[0]["sku"] == "SHARED-SKU"
        assert b.get("/api/products").json()[0]["sku"] == "OTHER-SKU"
        cross_stock = b.post("/api/stock/receive", headers=hb,
                    json={"warehouse_id": wa, "sku": "OTHER-SKU", "quantity": 3})
        assert cross_stock.status_code == 404
        cross_order = b.post("/api/orders", headers=hb,
                    json=order_request(wa, [{"sku": "OTHER-SKU", "quantity": 1}]))
        assert cross_order.status_code == 404
        owner_order = a.post("/api/orders", headers=ha,
                    json=order_request(wa, [{"sku": "SHARED-SKU", "quantity": 1}])).json()["id"]
        assert b.post(f"/api/orders/{owner_order}/cancel", headers=hb).status_code == 404
        assert b.get("/api/movements").json()[0]["sku"] == "OTHER-SKU"
    db.dispose()


def test_catalog_csv_import_and_export(client):
    headers = register(client)
    content = b"sku,name,price_cents,reorder_point,unit\nSKU-1,Widgets,400,10,each\nSKU-2,Gadgets,250,4,box\n"
    response = client.post("/api/import/products", headers=headers,
                  files={"file": ("products.csv", io.BytesIO(content), "text/csv")})
    assert response.status_code == 200, response.text
    assert response.json() == {"created": 2, "skipped": 0}
    response = client.post("/api/import/products", headers=headers,
                  files={"file": ("products.csv", io.BytesIO(content), "text/csv")})
    assert response.json() == {"created": 0, "skipped": 2}
    assert len(client.get("/api/products").json()) == 2
    assert "SKU-1" in client.get("/api/export/inventory.csv").text


def test_bad_import_is_transactional(client):
    headers = register(client)
    bad = b"sku,name,price_cents\nGOOD,Good product,50\nBAD,Bad product,not-number\n"
    response = client.post("/api/import/products", headers=headers,
                  files={"file": ("bad.csv", io.BytesIO(bad), "text/csv")})
    assert response.status_code == 400
    assert client.get("/api/products").json() == []


def test_passwords_are_salted_and_verified():
    p = hash_password("a-secure-password")
    q = hash_password("a-secure-password")
    assert p != q
    assert verify_password("a-secure-password", p)
    assert not verify_password("wrong-password", p)


def test_production_requires_secret_and_database(monkeypatch):
    from dispatchforge_app.settings import load_settings
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("APP_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="APP_SECRET"):
        load_settings()
    monkeypatch.setenv("APP_SECRET", "a" * 40)
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        load_settings()


def test_employee_cannot_modify_catalog_but_can_receive(client):
    headers = register(client)
    wid = add_stock(client, headers)
    from dispatchforge_app.models import User
    with client.test_db.SessionLocal() as session:
        owner = session.scalar(select(User).where(User.email == "owner@example.com"))
        owner.role = "staff"  # Simulate a provisioned employee account.
        session.commit()
    forbidden = client.post("/api/products", headers=headers, json={"sku": "NEW", "name": "New"})
    assert forbidden.status_code == 403
    received = client.post("/api/stock/receive", headers=headers,
                  json={"warehouse_id": wid, "sku": "PRODUCT-1", "quantity": 2})
    assert received.status_code == 200
    assert client.get("/api/inventory").json()[0]["on_hand"] == 22


def test_duplicate_order_lines_aggregate_quantity(client):
    headers = register(client)
    wid = add_stock(client, headers)
    result = client.post("/api/orders", headers=headers, json=order_request(wid, [
        {"sku": "PRODUCT-1", "quantity": 3}, {"sku": "PRODUCT-1", "quantity": 4}]))
    assert result.status_code == 201
    stock = client.get("/api/inventory").json()[0]
    assert stock["reserved"] == 7
    assert client.get("/api/orders").json()[0]["items"] == [{"sku": "PRODUCT-1", "quantity": 7}]


def test_bad_date_and_missing_product_rejected_without_changes(client):
    headers = register(client)
    wid = add_stock(client, headers)
    past = order_request(wid)
    past["due_date"] = "2000-01-01"
    assert client.post("/api/orders", headers=headers, json=past).status_code == 400
    unknown = order_request(wid, [{"sku": "UNKNOWN", "quantity": 1}])
    assert client.post("/api/orders", headers=headers, json=unknown).status_code == 404
    assert client.get("/api/inventory").json()[0]["reserved"] == 0


def test_export_guards_against_spreadsheet_formula_injection(client):
    headers = register(client)
    response = client.post("/api/products", headers=headers,
                json={"sku": "SAFE-SKU", "name": "=CMD('danger')"})
    assert response.status_code == 201
    csv_content = client.get("/api/export/inventory.csv").text
    assert "'=CMD" in csv_content
    assert "\r\n" in csv_content


def test_supplier_ownership_and_dashboard_counts(client):
    headers = register(client)
    created = client.post("/api/suppliers", headers=headers,
             json={"name": "Sample Supplier", "email": "sup@example.com"})
    assert created.status_code == 201
    assert client.get("/api/suppliers").json() == [{"id": created.json()["id"],
                     "name": "Sample Supplier", "email": "sup@example.com"}]
    assert client.get("/api/overview").json()["warehouses"] == 1
