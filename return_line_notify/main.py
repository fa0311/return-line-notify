import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .api import api
from .environ import Environ
from .health import health
from .logger import init_logger
from .metrics import MetricsController, registry
from .service import LineWorksService

environ = Environ()
init_logger(environ.log_path)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    service = LineWorksService(environ)
    app.state.service = service
    await service.start()
    up_time = asyncio.create_task(MetricsController.up_time())
    try:
        yield
    finally:
        up_time.cancel()
        await service.stop()


app = FastAPI(lifespan=lifespan)
app.include_router(api, prefix="/api")
app.include_router(health)


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3333)
