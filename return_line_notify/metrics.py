import asyncio
import time
from types import TracebackType

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
)

registry = CollectorRegistry()


up_time_seconds = Counter(
    "line_notify_up_time_seconds",
    "Total uptime in seconds",
    registry=registry,
)


messages_sent = Counter(
    "line_notify_messages_sent",
    "Total number of messages sent",
    ["channel_no", "message_type", "status"],
    registry=registry,
)


message_send_duration_seconds = Histogram(
    "line_notify_message_send_duration_seconds",
    "Message send duration in seconds",
    ["channel_no", "message_type"],
    registry=registry,
    buckets=[0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 10],
)


messages_received = Counter(
    "line_notify_messages_received",
    "Total number of messages received",
    ["channel_no"],
    registry=registry,
)

connected = Gauge(
    "line_notify_connected",
    "1 while the MQTT connection to LINE WORKS is established",
    registry=registry,
)

reconnects_total = Counter(
    "line_notify_reconnects_total",
    "Number of times the MQTT connection was re-established",
    registry=registry,
)

connection_errors_total = Counter(
    "line_notify_connection_errors_total",
    "Number of LINE WORKS sessions that ended with an error",
    registry=registry,
)

last_received_timestamp_seconds = Gauge(
    "line_notify_last_received_timestamp_seconds",
    "Unix time of the last MQTT packet received from LINE WORKS",
    registry=registry,
)


class MetricsController:
    @staticmethod
    def received(channel_no: str | int) -> None:
        messages_received.labels(channel_no).inc()

    @staticmethod
    def packet_received() -> None:
        last_received_timestamp_seconds.set(time.time())

    @staticmethod
    def set_connected(value: bool) -> None:
        connected.set(1 if value else 0)

    @staticmethod
    def reconnected() -> None:
        reconnects_total.inc()

    @staticmethod
    def connection_error() -> None:
        connection_errors_total.inc()

    @staticmethod
    async def up_time() -> None:
        while True:
            up_time_seconds.inc()
            await asyncio.sleep(1)


class SendMessageMetrics:
    def __init__(self, channel_no: str | int, type: str) -> None:
        self.channel_no = channel_no
        self.type = type

    def __enter__(self) -> None:
        self.start_time = time.time()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        duration = time.time() - self.start_time
        message_send_duration_seconds.labels(self.channel_no, self.type).observe(
            duration
        )
        messages_sent.labels(self.channel_no, self.type, "total").inc()
        if exc_type is None:
            messages_sent.labels(self.channel_no, self.type, "success").inc()
        else:
            messages_sent.labels(self.channel_no, self.type, "failure").inc()
