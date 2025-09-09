import asyncio

import uvicorn
from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from line_works.client import LineWorks
from line_works.mqtt.enums.packet_type import PacketType
from line_works.tracer import LineWorksTracer
from prometheus_client import make_asgi_app
import logging

from .api import api, line_works_depends
from .depends.line_sticker import line_works_sticker_depends
from .environ import Environ
from .line_works import receive_publish_packet
from .logger import init_logger
from .metrics import MetricsController, registry

environ = Environ()


async def connect(works_id: str, password: str):
    while True:
        works = LineWorks(works_id=works_id, password=password)
        line_works_depends.init(works)
        line_works_sticker_depends.init(works)
        tracer = LineWorksTracer(works=works)
        tracer.add_trace_func(PacketType.PUBLISH, receive_publish_packet)
        try:
            await tracer.connect()
        except Exception as e:
            logging.error("Failed to connect to Line Works", exc_info=e)
            await tracer.disconnect()



@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(connect(environ.works_id, environ.password))
    asyncio.create_task(MetricsController.up_time())

    yield



app = FastAPI(lifespan=lifespan)
app.include_router(api, prefix="/api")
app.mount("/metrics", make_asgi_app(registry))
init_logger(environ.log_path)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
