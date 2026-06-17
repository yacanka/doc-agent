from pathlib import Path

import pytest


def test_ui_assets_are_localhost_relative() -> None:
    for asset_path in ["app/ui/index.html", "app/ui/app.js", "app/ui/styles.css"]:
        content = Path(asset_path).read_text(encoding="utf-8")
        assert "https://" not in content
        assert "http://" not in content


def test_ui_static_entrypoint_contains_required_panels() -> None:
    content = Path("app/ui/index.html").read_text(encoding="utf-8")

    for expected in ["Upload one document", "Chat", "Document info", "Operation preview", "Download output"]:
        assert expected in content


@pytest.fixture(name="client")
def fixture_client():
    pytest.importorskip("fastapi")
    pytest.importorskip("multipart")
    testclient = pytest.importorskip("fastapi.testclient")
    from app.main import app

    return testclient.TestClient(app)


def test_root_redirects_to_ui(client) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code in {307, 308}
    assert response.headers["location"] == "/ui/index.html"


def test_health_reports_offline_readiness(client) -> None:
    from app.main import config

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["config"]["host"] == config.host
    assert "offline_ready" in response.json()


def test_download_output_uses_controlled_directory(client) -> None:
    from app.main import config

    output = config.outputs_dir / "ui-test-output.txt"
    output.write_text("done", encoding="utf-8")

    response = client.get("/outputs/ui-test-output.txt")

    assert response.status_code == 200
    assert response.text == "done"


def test_localhost_middleware_rejects_remote_clients() -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("multipart")
    testclient = pytest.importorskip("fastapi.testclient")
    from app.main import app

    with testclient.TestClient(app, client=("203.0.113.10", 1234)) as remote_client:
        response = remote_client.get("/health")

    assert response.status_code == 403
