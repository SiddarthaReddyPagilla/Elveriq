"""Consistent product identity and muted theme across the public and demo UI."""
from pathlib import Path

from fastapi.testclient import TestClient
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app


def test_brand_name_and_shared_theme(tmp_path):
    url = f"sqlite:///{tmp_path / 'brand-check.sqlite3'}"
    db = Database(url)
    with TestClient(create_app(db, Settings('development', 'branding-test-secret', url))) as client:
        homepage = client.get('/')
        assert homepage.status_code == 200
        assert '<title>Elveriq | Warehouse Management</title>' in homepage.text
        assert 'class="brand-cloud"' not in homepage.text
        assert 'Elveriq Cloud' not in homepage.text
        assert '/static/brand.css' in homepage.text
        assert 'Warehouse management software' in homepage.text
        dashboard = client.get('/demo')
        assert dashboard.status_code == 200
        assert 'class="brand-cloud"' not in dashboard.text
        assert '/static/brand.css' in dashboard.text
        css = client.get('/static/brand.css')
        assert css.status_code == 200
        assert '--elveriq-pine:' in css.text
        assert '--elveriq-cream:' in css.text
    db.dispose()


def test_brand_styles_do_not_modify_warehouse_logic():
    css = Path(__file__).parents[1] / 'dispatchforge_app' / 'static' / 'brand.css'
    assert css.exists()
    assert 'cinema-statement' in css.read_text()
    assert 'status-low' in css.read_text()
