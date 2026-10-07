from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from .api import get_service
from .service import LineWorksService

health = APIRouter()


@health.get("/health")
async def status(
    service: LineWorksService = Depends(get_service),
) -> JSONResponse:
    ok, detail = service.health()
    content: dict[str, Any] = detail
    return JSONResponse(content, status_code=200 if ok else 503)
