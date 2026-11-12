from fastapi.testclient import TestClient
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app


def test_operational_dashboard_routes_and_assets(tmp_path):
    url=f"sqlite:///{tmp_path / 'ui.sqlite3'}"
    db=Database(url)
    with TestClient(create_app(db,Settings('development','dashboard-secret',url))) as c:
        html=c.get('/demo').text
        for section in ('transfers','counts','returns','replenishment'):
            assert f'data-view="{section}"' in html
        assert 'data-view="team"' not in html
        assert c.get('/join').status_code==200
        assert 'Join a warehouse workspace' in c.get('/join').text
        assert 'URLSearchParams' in c.get('/static/join.js').text
        assert 'data-section="transfers"' in html
        assert c.get('/static/app.js').status_code==200
    db.dispose()
