from fastapi.testclient import TestClient
from app.main import create_app


def test_updated_interface_revalidates_scripts_styles_and_html(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        for path in ["/", "/index.html", "/app.js?v=0.3.1", "/brief.js?v=0.3.1", "/style.css?v=0.3.1"]:
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-cache"
            cached = client.get(path, headers={"If-None-Match": response.headers["etag"]})
            assert cached.status_code == 304
            assert cached.headers["cache-control"] == "no-cache"
        assert client.get("/api/config").headers["cache-control"] == "no-store"
