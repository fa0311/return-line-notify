import asyncio
import logging
import os
from logging import StreamHandler
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.concurrency import asynccontextmanager
from line_works.client import LineWorks
from line_works.mqtt.enums.packet_type import PacketType
from line_works.mqtt.models.packet import MQTTPacket
from line_works.mqtt.models.payload.message import MessagePayload
from line_works.tracer import LineWorksTracer

from .environ import Environ


def receive_publish_packet(w: LineWorks, p: MQTTPacket) -> None:
    payload = p.payload

    if not isinstance(payload, MessagePayload):
        return

    if not payload.channel_no or not payload.from_user_no:
        return

    channel_no = str(payload.channel_no)

    if payload.loc_args1 == "/test":
        w.send_text_message(payload.channel_no, "ok")

    elif payload.loc_args1 == "/channel":
        w.send_text_message(payload.channel_no, f"channel_no: {channel_no}")


def init_log(path: Path) -> None:
    os.makedirs(path.parent, exist_ok=True)

    stream_handler = StreamHandler()
    stream_handler.setLevel(logging.INFO)
    file_handler = TimedRotatingFileHandler(
        filename=path,
        when="D",
        interval=1,
        backupCount=90,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[stream_handler, file_handler],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(tracer.connect())

    yield

    await tracer._ws.close()


app = FastAPI(lifespan=lifespan)

environ = Environ()
works = LineWorks(works_id=environ.works_id, password=environ.password)
tracer = LineWorksTracer(works=works)
tracer.add_trace_func(PacketType.PUBLISH, receive_publish_packet)
init_log(environ.log_path)


@app.post("/api/notify")
async def notify(request: Request, authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=400, detail="Invalid or missing Authorization header"
        )

    bearer_token = authorization.split("Bearer ")[1]

    content_type = request.headers.get("content-type", "").lower()
    if not content_type.startswith("application/x-www-form-urlencoded"):
        raise HTTPException(
            status_code=400,
            detail="Content-Type must be application/x-www-form-urlencoded",
        )

    form = await request.form()
    message = form.get("message")

    if not isinstance(message, str):
        raise HTTPException(status_code=400, detail="Missing 'message' in form data")

    works.send_text_message(int(bearer_token), message)

    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
