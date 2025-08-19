import asyncio

import uvicorn
from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from line_works.client import LineWorks
from line_works.mqtt.enums.packet_type import PacketType
from line_works.tracer import LineWorksTracer
from prometheus_client import make_asgi_app

from .api import api, line_works_depends
from .depends.line_sticker import line_works_sticker_depends
from .environ import Environ
from .line_works import receive_publish_packet
from .logger import init_logger
from .metrics import MetricsController, registry

environ = Environ()


@asynccontextmanager
async def lifespan(app: FastAPI):
    works = LineWorks(works_id=environ.works_id, password=environ.password)
    line_works_depends.init(works)
    line_works_sticker_depends.init(works)
    tracer = LineWorksTracer(works=works)
    tracer.add_trace_func(PacketType.PUBLISH, receive_publish_packet)
    asyncio.create_task(tracer.connect())
    asyncio.create_task(MetricsController.up_time())

    yield

    await tracer.disconnect()


app = FastAPI(lifespan=lifespan)
app.include_router(api, prefix="/api")
app.mount("/metrics", make_asgi_app(registry))
init_logger(environ.log_path)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
