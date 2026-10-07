import asyncio
import os
from typing import Any, Callable, Optional

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from return_line_notify.api import api
from return_line_notify.environ import Environ
from return_line_notify.health import health
from return_line_notify.metrics import registry
from return_line_notify.service import LineWorksService


def make_environ(**overrides: Any) -> Environ:
    values: dict[str, Any] = {
        "WORKS_ID": "test@example",
        "PASSWORD": "secret",
        "UNHEALTHY_EXIT_SEC": 0,
        "RECONNECT_BACKOFF_MAX_SEC": 0.05,
    }
    values.update(overrides)
    return Environ(_env_file=None, **values)  # type: ignore[call-arg]


class FakeWorks:
    """LineWorks の送信メソッドだけを模倣する"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fail_with: Optional[BaseException] = None
        self.relogin_result = False

    def _record(self, name: str, *args: Any) -> dict[str, str]:
        if self.fail_with is not None:
            raise self.fail_with
        self.calls.append((name, args))
        return {"result": "ok"}

    def send_text_message(self, to: int, text: str) -> dict[str, str]:
        return self._record("text", to, text)

    def send_sticker_message(self, to: int, sticker: Any) -> dict[str, str]:
        return self._record("sticker", to, sticker)

    def send_image_message_with_file(
        self, to: int, channel_type: Any, data: bytes, name: str
    ) -> dict[str, str]:
        return self._record("image", to, channel_type, data, name)

    def ensure_login(self) -> bool:
        return self.relogin_result


def make_app(service: LineWorksService) -> FastAPI:
    app = FastAPI()
    app.state.service = service
    app.include_router(api, prefix="/api")
    app.include_router(health)

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    return app


@pytest.fixture
def fake_works() -> FakeWorks:
    return FakeWorks()


@pytest.fixture
def service(fake_works: FakeWorks) -> LineWorksService:
    """start() していない (バックグラウンド接続なし) サービス"""
    svc = LineWorksService(make_environ())
    svc.works = fake_works  # type: ignore[assignment]
    return svc


@pytest.fixture
def client(service: LineWorksService) -> TestClient:
    return TestClient(make_app(service))


def run(coro: Callable[[], Any]) -> Any:
    return asyncio.run(coro())


def integration_enabled() -> bool:
    return os.environ.get("RLN_INTEGRATION") == "1"
