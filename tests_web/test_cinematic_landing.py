"""Public marketing page: asset integrity and noninterference with warehouse operations."""
from pathlib import Path

from fastapi.testclient import TestClient
from dispatchforge_app.database import Database
from dispatchforge_app.settings import Settings
from dispatchforge_app.web import create_app


ASSETS = (
    "warehouse-hero.webp",
    "warehouse-receiving.webp",
    "warehouse-storage.webp",
    "warehouse-picking.webp",
)


def test_cinematic_warehouse_landing_and_assets(tmp_path):
    url = f"sqlite:///{tmp_path / 'cinematic-ui.sqlite3'}"
    db = Database(url)
    with TestClient(create_app(db, Settings("development", "test-cinematic-secret", url))) as client:
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        assert 'class="cinematic-page"' in html
        assert 'href="/demo"' in html
        assert 'href="/register"' in html
        assert 'href="#main-content"' in html
        assert 'data-word-reveal' in html
        assert html.count('class="cinema-step"') == 4
        assert '/static/real_video.js' not in html
        assert '<video' not in html
        assert 'cinema-stage-overlays' not in html
        assert 'Elveriq Cloud' not in html
        for idx in range(4):
            assert f'data-stage="{idx}"' in html
            assert f'data-stage-photo="{idx}"' in html
        for filename in ASSETS:
            assert f'/static/media/{filename}' in html
            image = client.get(f"/static/media/{filename}")
            assert image.status_code == 200
            assert image.headers["content-type"].startswith("image/webp")
            assert len(image.content) > 10000
        css = client.get('/static/cinematic.css')
        assert css.status_code == 200
        assert 'prefers-reduced-motion' in css.text
        assert 'cinema-stage-sticky' in css.text
        js = client.get('/static/cinematic.js')
        assert js.status_code == 200
        assert 'IntersectionObserver' in js.text
        assert 'requestAnimationFrame' in js.text
        # Preserve the existing transactional application and demo routing.
        assert client.get('/demo').status_code == 200
        assert client.get('/api/health').status_code == 200
    db.dispose()


def test_image_payloads_are_reasonably_small():
    root = Path(__file__).parents[1] / 'dispatchforge_app' / 'static' / 'media'
    for name in ASSETS:
        assert (root / name).stat().st_size < 350_000, name
