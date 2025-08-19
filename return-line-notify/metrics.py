import asyncio
import time

from prometheus_client import (
    CollectorRegistry,
    Counter,
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
)


messages_received = Counter(
    "line_notify_messages_received",
    "Total number of messages received",
    ["channel_no"],
    registry=registry,
)


class MetricsController:
    @staticmethod
    def received(channel_no: str | int):
        messages_received.labels(channel_no).inc()

    @staticmethod
    async def up_time():
        while True:
            up_time_seconds.inc()
            await asyncio.sleep(1)


class SendMessageMetrics:
    def __init__(self, channel_no: str | int, type: str):
        self.channel_no = channel_no
        self.type = type

    def __enter__(self):
        self.start_time = time.time()

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        message_send_duration_seconds.labels(self.channel_no, self.type).observe(
            duration
        )
        messages_sent.labels(self.channel_no, self.type, "total").inc()
        if exc_type is None:
            messages_sent.labels(self.channel_no, self.type, "success").inc()
        else:
            messages_sent.labels(self.channel_no, self.type, "failure").inc()
