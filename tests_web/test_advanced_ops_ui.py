"""Smoke check for authenticated advanced workspaces and no accidental demo mutation UI."""
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app
from fastapi.testclient import TestClient
from tests_web.test_warehouse_web import register


def test_advanced_operations_navigation_and_scanner_forms(tmp_path):
    url=f"sqlite:///{tmp_path/'advanced-ui.sqlite3'}"
    db=Database(url)
    with TestClient(create_app(db,Settings('development','advanced-ui-test',url))) as c:
        register(c)
        html=c.get('/app').text
        for token in ('data-section="inbound"','data-section="exceptions"',
                      'data-section="shipping"','id="asn-create-form"','id="asn-scan-form"',
                      'id="ops-case-form"','id="ops-milestone-form"',
                      '/static/advanced_ops.js'):
            assert token in html
        assert c.get('/static/advanced_ops.js').status_code==200
        demo=c.get('/demo').text
        assert '/static/advanced_ops.js' not in demo
        assert 'id="ops-case-form"' not in demo
    db.dispose()
