"""Public and application pages share the same assets without changing warehouse routes."""
from fastapi.testclient import TestClient
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app


def test_unified_public_demo_and_auth_pages(tmp_path):
    url = f"sqlite:///{tmp_path / 'ui-check.sqlite3'}"
    database = Database(url)
    try:
        with TestClient(create_app(database, Settings('development', 'ui-check-secret', url))) as client:
            for path in ('/', '/demo', '/login', '/register'):
                page = client.get(path)
                assert page.status_code == 200, path
                assert '/static/brand.css' in page.text, path
                assert 'class="brand-cloud"' not in page.text, path
                assert 'Elveriq Cloud' not in page.text, path
            homepage = client.get('/').text
            assert homepage.count('class="cinema-step"') == 4
            assert '<video' not in homepage
            assert 'cinema-stage-overlays' not in homepage
            for i in range(4):
                assert f'data-stage-photo="{i}"' in homepage
            for path in ('/static/brand.css', '/static/cinematic.css', '/static/cinematic.js'):
                assert client.get(path).status_code == 200, path
            for image in ('warehouse-hero.webp','warehouse-storage.webp','warehouse-receiving.webp','warehouse-picking.webp'):
                media = client.get('/static/media/' + image)
                assert media.status_code == 200
                assert media.headers['content-type'] == 'image/webp'
                assert len(media.content) > 10000
            css = client.get('/static/brand.css').text
            assert "body:has(#workspace) .dashboard-top" in css
            assert "body:has(.auth-wrap) .auth-wrap" in css
            assert '/static/media/warehouse-storage.webp' in css
            assert '/static/media/warehouse-receiving.webp' in css
            assert client.get('/api/health').status_code == 200
    finally:
        database.dispose()
