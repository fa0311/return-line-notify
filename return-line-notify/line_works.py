from line_works.client import LineWorks
from line_works.mqtt.models.packet import MQTTPacket
from line_works.mqtt.models.payload.message import MessagePayload

from .metrics import MetricsController, SendMessageMetrics


def receive_publish_packet(w: LineWorks, p: MQTTPacket) -> None:
    payload = p.payload

    if not isinstance(payload, MessagePayload):
        return

    if not payload.channel_no or not payload.from_user_no:
        return

    channel_no = str(payload.channel_no)
    channel_type = str(payload.channel_type)

    MetricsController.received(channel_no)

    if payload.loc_args1 == "/test":
        with SendMessageMetrics(channel_no, "command"):
            w.send_text_message(payload.channel_no, "ok")

    elif payload.loc_args1 == "/notify":
        with SendMessageMetrics(channel_no, "command"):
            w.send_text_message(payload.channel_no, f"{channel_no}:{channel_type}")
