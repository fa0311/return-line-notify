import asyncio
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

from line_works.client import LineWorks
from line_works.mqtt.enums.packet_type import PacketType
from line_works.mqtt.exceptions import PacketParseException
from line_works.mqtt.models.packet import MQTTPacket
from line_works.mqtt.models.payload.message import MessagePayload
from line_works.tracer import LineWorksTracer

from .depends.line_sticker import LineWorksSticker, load_sticker_config
from .environ import Environ
from .metrics import MetricsController, SendMessageMetrics

T = TypeVar("T")

logger = logging.getLogger(__name__)

# この秒数以上つながっていた接続が切れた場合はバックオフをリセットする
STABLE_CONNECTION_SEC = 60
WATCHDOG_INTERVAL_SEC = 5


class ServiceNotReady(Exception):
    """LINE WORKS にまだログインできていない"""


class ConnectionState(str, Enum):
    STARTING = "starting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class LineWorksService:
    """LINE WORKS のログイン・MQTT 接続・送信を一手に引き受ける。

    - MQTT は切れたら指数バックオフで繋ぎ直し、定期的に再ログインする
    - LINE WORKS への同期 HTTP 呼び出しは専用スレッドで直列に実行し、
      イベントループを止めない
    - 別スレッドの watchdog が、長時間の未接続やイベントループの停止を
      検出したらプロセスを終了する (Docker に再起動させる)
    """

    def __init__(self, environ: Environ) -> None:
        self.environ = environ
        self.works: Optional[LineWorks] = None
        self.sticker: Optional[LineWorksSticker] = None
        self.state = ConnectionState.STARTING
        self.last_error: Optional[str] = None
        self.connected_at: Optional[float] = None
        self.disconnected_at: float = time.monotonic()
        self.session_count = 0
        self._tracer: Optional[LineWorksTracer] = None
        self._reconnect_requested: Optional[asyncio.Event] = None
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="line-works"
        )
        self._task: Optional[asyncio.Task[None]] = None
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._heartbeat = time.monotonic()
        self._watchdog_stop = threading.Event()
        self._watchdog: Optional[threading.Thread] = None

    # ------------------------------------------------------------ lifecycle

    async def start(self) -> None:
        self._reconnect_requested = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="line-works-run")
        self._heartbeat_task = asyncio.create_task(
            self._beat(), name="line-works-heartbeat"
        )
        if self.environ.unhealthy_exit > 0:
            self._watchdog = threading.Thread(
                target=self._watch, name="line-works-watchdog", daemon=True
            )
            self._watchdog.start()

    async def stop(self) -> None:
        self._watchdog_stop.set()
        for task in (self._task, self._heartbeat_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------ public API

    def request_reconnect(self, reason: str) -> None:
        logger.info(f"Reconnect requested: {reason}")
        if self._reconnect_requested is not None:
            self._reconnect_requested.set()

    async def call(self, fn: Callable[[LineWorks], T]) -> T:
        """LINE WORKS クライアントの同期メソッドを専用スレッドで実行する"""
        works = self.works
        if works is None:
            raise ServiceNotReady(self.last_error or "not logged in yet")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, fn, works)

    async def verify_session(self) -> None:
        """送信失敗のあとにセッションを検証し、必要なら繋ぎ直す"""
        try:
            relogged = await self.call(lambda w: w.ensure_login())
        except ServiceNotReady:
            return
        except Exception as e:
            logger.warning(f"Session verification failed: {e!r}")
            self.request_reconnect("session verification failed")
            return
        if relogged:
            self.request_reconnect("session was renewed")

    def health(self) -> tuple[bool, dict[str, Any]]:
        """MQTT が接続中 (CONNACK 受信済みでソケットが開いている) なら OK"""
        now = time.monotonic()
        tracer = self._tracer
        last_received = tracer.last_received_at if tracer else None
        received_ago = now - last_received if last_received else None
        ok = self.state == ConnectionState.CONNECTED
        detail: dict[str, Any] = {
            "status": "ok" if ok else "degraded",
            "state": self.state.value,
            "logged_in": self.works is not None,
            "connected_for_sec": (
                round(now - self.connected_at) if self.connected_at else None
            ),
            "last_received_sec_ago": (
                round(received_ago) if received_ago is not None else None
            ),
            "session_count": self.session_count,
            "last_error": self.last_error,
        }
        return ok, detail

    # ------------------------------------------------------------ internals

    async def _run(self) -> None:
        backoff = min(1.0, self.environ.reconnect_backoff_max)
        while True:
            started = time.monotonic()
            try:
                await self._session()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.last_error = repr(e)
                MetricsController.connection_error()
                logger.error(f"LINE WORKS session ended: {e!r}", exc_info=e)
            self._mark_disconnected()

            if time.monotonic() - started > STABLE_CONNECTION_SEC:
                backoff = min(1.0, self.environ.reconnect_backoff_max)
            logger.info(f"Reconnecting to LINE WORKS in {backoff:.0f}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self.environ.reconnect_backoff_max)

    async def _session(self) -> None:
        """ログインから MQTT 切断までの 1 セッション"""
        assert self._reconnect_requested is not None
        works = await asyncio.to_thread(self._login)
        self.works = works
        self.last_error = None
        try:
            self.sticker = await asyncio.to_thread(load_sticker_config, works)
        except Exception as e:
            logger.warning(f"Failed to load sticker config: {e!r}")

        tracer = LineWorksTracer(
            works=works,
            idle_timeout=self.environ.mqtt_idle_timeout or None,
        )
        tracer.add_trace_func(PacketType.CONNACK, self._on_connack)
        tracer.add_trace_func(PacketType.PUBLISH, self._on_publish)
        self._tracer = tracer
        self._reconnect_requested.clear()

        connect = asyncio.create_task(tracer.connect(), name="mqtt-connect")
        waiter = asyncio.create_task(
            self._reconnect_requested.wait(), name="reconnect-wait"
        )
        try:
            done, _ = await asyncio.wait(
                {connect, waiter},
                timeout=self.environ.relogin_interval,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if connect in done:
                connect.result()
                raise RuntimeError("MQTT connection closed unexpectedly")
            reason = "reconnect requested" if waiter in done else "periodic re-login"
            logger.info(f"Closing MQTT connection: {reason}")
            await tracer.disconnect()
            await connect
        finally:
            waiter.cancel()
            connect.cancel()
            await asyncio.gather(connect, waiter, return_exceptions=True)
            self._tracer = None

    def _login(self) -> LineWorks:
        return LineWorks(
            works_id=self.environ.works_id,
            password=self.environ.password,
            request_timeout=self.environ.http_timeout,
        )

    def _mark_disconnected(self) -> None:
        if self.state == ConnectionState.CONNECTED:
            self.disconnected_at = time.monotonic()
        self.state = ConnectionState.DISCONNECTED
        self.connected_at = None
        MetricsController.set_connected(False)

    def _on_connack(self, works: LineWorks, packet: MQTTPacket) -> None:
        if self.session_count > 0:
            MetricsController.reconnected()
        self.session_count += 1
        self.state = ConnectionState.CONNECTED
        self.connected_at = time.monotonic()
        MetricsController.set_connected(True)
        MetricsController.packet_received()
        logger.info(f"LINE WORKS connected (session #{self.session_count})")

    async def _on_publish(self, works: LineWorks, packet: MQTTPacket) -> None:
        MetricsController.packet_received()
        try:
            payload = packet.payload
        except (PacketParseException, ValueError) as e:
            logger.debug(f"Ignoring PUBLISH: {e}")
            return

        if not isinstance(payload, MessagePayload):
            return
        if not payload.channel_no or not payload.from_user_no:
            return

        channel_no = payload.channel_no
        channel_type = str(payload.channel_type)
        MetricsController.received(channel_no)

        command = payload.loc_args1
        if command == "/test":
            await self._send_command(channel_no, "ok")
        elif command == "/notify":
            await self._send_command(channel_no, f"{channel_no}:{channel_type}")
        elif command == "/reconnect":
            self.request_reconnect("/reconnect command")

    async def _send_command(self, channel_no: int, text: str) -> None:
        try:
            with SendMessageMetrics(channel_no, "command"):
                await self.call(lambda w: w.send_text_message(channel_no, text))
        except Exception as e:
            logger.error(f"Failed to reply to command: {e!r}")

    async def _beat(self) -> None:
        while True:
            self._heartbeat = time.monotonic()
            await asyncio.sleep(1)

    def _watch(self) -> None:
        limit = self.environ.unhealthy_exit
        while not self._watchdog_stop.wait(WATCHDOG_INTERVAL_SEC):
            now = time.monotonic()
            stalled = now - self._heartbeat
            if stalled > limit:
                self._die(f"event loop has been stalled for {stalled:.0f}s")
            if self.state != ConnectionState.CONNECTED:
                down = now - self.disconnected_at
                if down > limit:
                    self._die(f"not connected for {down:.0f}s")

    @staticmethod
    def _die(reason: str) -> None:
        logger.critical(f"Watchdog: {reason}; exiting for restart")
        logging.shutdown()
        os._exit(70)
