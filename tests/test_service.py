import asyncio
from typing import Any, Callable, Optional

import pytest
from line_works.mqtt.enums.packet_type import PacketType

from return_line_notify import service as service_module
from return_line_notify.service import ConnectionState, LineWorksService
from tests.conftest import FakeWorks, make_environ


class FakeTracer:
    """LineWorksTracer の connect/disconnect だけを模倣する"""

    instances: list["FakeTracer"] = []
    # 各接続の筋書き: None=disconnect されるまで待つ / 例外=その例外で切れる
    script: list[Optional[BaseException]] = []

    def __init__(self, works: Any, idle_timeout: float) -> None:
        self.works = works
        self.idle_timeout = idle_timeout
        self.trace: dict[PacketType, Callable[..., Any]] = {}
        self.last_received_at: Optional[float] = None
        self._closed = asyncio.Event()
        self.disconnect_called = False
        FakeTracer.instances.append(self)

    def add_trace_func(self, t: PacketType, f: Callable[..., Any]) -> None:
        self.trace[t] = f

    async def connect(self) -> None:
        outcome = FakeTracer.script.pop(0) if FakeTracer.script else None
        self.last_received_at = asyncio.get_running_loop().time()
        self.trace[PacketType.CONNACK](self.works, None)
        if outcome is not None:
            await asyncio.sleep(0.01)
            raise outcome
        await self._closed.wait()

    async def disconnect(self) -> None:
        self.disconnect_called = True
        self._closed.set()


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> FakeWorks:
    FakeTracer.instances = []
    FakeTracer.script = []
    works = FakeWorks()
    monkeypatch.setattr(service_module, "LineWorksTracer", FakeTracer)
    monkeypatch.setattr(service_module, "LineWorks", lambda **kw: works)
    monkeypatch.setattr(service_module, "load_sticker_config", lambda w: {"stub": True})
    monkeypatch.setattr(service_module, "STABLE_CONNECTION_SEC", 0)
    return works


async def wait_for(cond: Callable[[], bool], timeout: float = 2) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not cond():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met")
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_start_logs_in_and_connects(patched: FakeWorks) -> None:
    svc = LineWorksService(make_environ())
    await svc.start()
    try:
        await wait_for(lambda: svc.state == ConnectionState.CONNECTED)
        assert svc.works is patched
        assert svc.sticker == {"stub": True}
        ok, detail = svc.health()
        assert ok is True
        assert detail["session_count"] == 1
        result = await svc.call(lambda w: w.send_text_message(1, "x"))
        assert result == {"result": "ok"}
    finally:
        await svc.stop()


@pytest.mark.asyncio
async def test_reconnects_after_connection_error(patched: FakeWorks) -> None:
    FakeTracer.script = [RuntimeError("lost"), RuntimeError("lost again")]
    svc = LineWorksService(make_environ())
    await svc.start()
    try:
        await wait_for(lambda: svc.session_count == 3)
        assert svc.state == ConnectionState.CONNECTED
        assert "lost again" in (svc.last_error or "") or svc.last_error is None
        assert len(FakeTracer.instances) == 3
    finally:
        await svc.stop()


@pytest.mark.asyncio
async def test_request_reconnect_closes_and_reopens(
    patched: FakeWorks,
) -> None:
    svc = LineWorksService(make_environ())
    await svc.start()
    try:
        await wait_for(lambda: svc.state == ConnectionState.CONNECTED)
        first = FakeTracer.instances[0]
        svc.request_reconnect("test")
        await wait_for(lambda: svc.session_count == 2)
        assert first.disconnect_called is True
        assert svc.state == ConnectionState.CONNECTED
    finally:
        await svc.stop()


@pytest.mark.asyncio
async def test_periodic_relogin(patched: FakeWorks) -> None:
    svc = LineWorksService(make_environ(RELOGIN_INTERVAL_SEC=0.05))
    await svc.start()
    try:
        await wait_for(lambda: svc.session_count >= 3, timeout=3)
        assert all(t.disconnect_called for t in FakeTracer.instances[:-1])
    finally:
        await svc.stop()


@pytest.mark.asyncio
async def test_login_failure_is_retried(
    patched: FakeWorks, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = 0

    def flaky_login(**kw: Any) -> FakeWorks:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("login failed")
        return patched

    monkeypatch.setattr(service_module, "LineWorks", flaky_login)
    svc = LineWorksService(make_environ())
    await svc.start()
    try:
        assert svc.works is None
        with pytest.raises(service_module.ServiceNotReady):
            await svc.call(lambda w: w.send_text_message(1, "x"))
        await wait_for(lambda: svc.state == ConnectionState.CONNECTED)
        assert attempts == 3
        assert svc.works is patched
    finally:
        await svc.stop()


@pytest.mark.asyncio
async def test_command_reply_runs_in_executor(patched: FakeWorks) -> None:
    import json
    import struct

    from line_works.mqtt.models.packet import MQTTPacket
    from line_works.mqtt.packets import encode_remaining_length

    svc = LineWorksService(make_environ())
    await svc.start()
    try:
        await wait_for(lambda: svc.state == ConnectionState.CONNECTED)
        payload = {
            "domain_id": 1,
            "sType": 1,
            "ocn": 1,
            "nType": 1,
            "aBadge": 0,
            "badge": 0,
            "cBadge": 0,
            "hBadge": 0,
            "mBadge": 0,
            "wpaBadge": 0,
            "token": "t",
            "userNo": 2,
            "chNo": 3,
            "chType": 10,
            "fromUserNo": 4,
            "loc-key": "k",
            "loc-args1": "/test",
            "notification-id": "n",
        }
        body = json.dumps(payload).encode()
        variable = struct.pack("!H", 5) + b"topic" + struct.pack("!H", 1)
        raw = b"\x32" + encode_remaining_length(len(variable) + len(body))
        packet = MQTTPacket.parse_from_bytes(raw + variable + body)
        tracer = FakeTracer.instances[0]
        await tracer.trace[PacketType.PUBLISH](patched, packet)
        assert patched.calls == [("text", (3, "ok"))]
    finally:
        await svc.stop()


@pytest.mark.asyncio
async def test_watchdog_exits_when_disconnected_too_long(
    patched: FakeWorks, monkeypatch: pytest.MonkeyPatch
) -> None:
    died: list[str] = []
    monkeypatch.setattr(service_module, "WATCHDOG_INTERVAL_SEC", 0.01)
    monkeypatch.setattr(
        LineWorksService, "_die", staticmethod(lambda reason: died.append(reason))
    )
    monkeypatch.setattr(
        service_module,
        "LineWorks",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("never")),
    )
    svc = LineWorksService(make_environ(UNHEALTHY_EXIT_SEC=0.05))
    await svc.start()
    try:
        await wait_for(lambda: len(died) > 0)
        assert "not connected" in died[0]
    finally:
        await svc.stop()
