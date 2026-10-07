import time

import pytest
from fastapi.testclient import TestClient
from requests.exceptions import ReadTimeout

from return_line_notify.service import ConnectionState, LineWorksService
from tests.conftest import FakeWorks

TOKEN = {"Authorization": "Bearer 336355274:10"}


def test_notify_text(client: TestClient, fake_works: FakeWorks) -> None:
    res = client.post("/api/notify", headers=TOKEN, data={"message": "hi"})
    assert res.status_code == 200, res.text
    assert res.json() == {"status": "ok"}
    assert fake_works.calls == [("text", (336355274, "hi"))]


def test_notify_sticker(client: TestClient, fake_works: FakeWorks) -> None:
    res = client.post(
        "/api/notify",
        headers=TOKEN,
        data={"message": "hi", "stickerId": "1", "stickerPackageId": "2"},
    )
    assert res.status_code == 200, res.text
    assert [c[0] for c in fake_works.calls] == ["text", "sticker"]
    sticker = fake_works.calls[1][1][1]
    assert sticker.pkg_id == "2"
    assert sticker.stk_type == "line"  # スタンプ設定未取得なら LINE 扱い


def test_notify_image(client: TestClient, fake_works: FakeWorks) -> None:
    res = client.post(
        "/api/notify",
        headers=TOKEN,
        data={"message": "img"},
        files={"imageFile": ("sample.png", b"\x89PNG", "image/png")},
    )
    assert res.status_code == 200, res.text
    assert fake_works.calls[0] == ("text", (336355274, "img"))
    name, args = fake_works.calls[1]
    assert name == "image"
    assert args[2] == b"\x89PNG"
    assert args[3] == "sample.png"


def test_notify_requires_bearer(client: TestClient) -> None:
    res = client.post("/api/notify", data={"message": "hi"})
    assert res.status_code == 400


def test_notify_rejects_malformed_token(client: TestClient) -> None:
    res = client.post(
        "/api/notify",
        headers={"Authorization": "Bearer nope"},
        data={"message": "hi"},
    )
    assert res.status_code == 400


def test_notify_rejects_json(client: TestClient) -> None:
    res = client.post("/api/notify", headers=TOKEN, json={"message": "hi"})
    assert res.status_code == 415


def test_notify_when_not_logged_in(service: LineWorksService) -> None:
    from tests.conftest import make_app

    service.works = None
    client = TestClient(make_app(service))
    res = client.post("/api/notify", headers=TOKEN, data={"message": "hi"})
    assert res.status_code == 503


def test_notify_timeout_returns_504(client: TestClient, fake_works: FakeWorks) -> None:
    fake_works.fail_with = ReadTimeout("slow")
    res = client.post("/api/notify", headers=TOKEN, data={"message": "hi"})
    assert res.status_code == 504


def test_notify_upstream_error_returns_502(
    client: TestClient, fake_works: FakeWorks
) -> None:
    fake_works.fail_with = RuntimeError("boom")
    res = client.post("/api/notify", headers=TOKEN, data={"message": "hi"})
    assert res.status_code == 502
    assert "boom" in res.json()["detail"]


def test_upstream_error_triggers_session_check(
    client: TestClient, fake_works: FakeWorks, service: LineWorksService
) -> None:
    fake_works.fail_with = RuntimeError("boom")
    requested: list[str] = []
    service.request_reconnect = lambda reason: requested.append(reason)  # type: ignore[method-assign]
    fake_works.relogin_result = True

    # verify_session は背景タスクなので失敗時のみ ensure_login を呼ぶ
    fake_works.fail_with = None
    service.works = fake_works  # type: ignore[assignment]
    import asyncio

    asyncio.run(service.verify_session())
    assert requested == ["session was renewed"]


def test_reconnect_endpoint(client: TestClient, service: LineWorksService) -> None:
    requested: list[str] = []
    service.request_reconnect = lambda reason: requested.append(reason)  # type: ignore[method-assign]
    res = client.post("/api/reconnect")
    assert res.status_code == 200
    assert requested == ["POST /api/reconnect"]


def test_health_degraded_before_connect(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "degraded"
    assert body["state"] == "starting"


def test_health_ok_when_connected(
    client: TestClient, service: LineWorksService
) -> None:
    class Tracer:
        last_received_at = time.monotonic()

    service.state = ConnectionState.CONNECTED
    service.connected_at = time.monotonic()
    service._tracer = Tracer()  # type: ignore[assignment]
    res = client.get("/health")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "ok"


def test_metrics_served_without_redirect(client: TestClient) -> None:
    res = client.get("/metrics", follow_redirects=False)
    assert res.status_code == 200
    assert "line_notify_connected" in res.text
    assert "line_notify_messages_sent" in res.text


@pytest.mark.parametrize("path", ["/health", "/metrics"])
def test_quiet_paths_are_filtered_from_access_log(path: str) -> None:
    import logging

    from return_line_notify.logger import AccessLogFilter

    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1", "GET", path, "1.1", 200),
        None,
    )
    assert AccessLogFilter().filter(record) is False
    record.args = ("127.0.0.1:1", "POST", "/api/notify", "1.1", 200)
    assert AccessLogFilter().filter(record) is True
