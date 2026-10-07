import logging
import socket

import urllib3.exceptions
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from line_works.client import ChannelType, LineWorks, Sticker
from requests.exceptions import Timeout
from starlette.datastructures import UploadFile

from .depends.bearer import bearer_token
from .depends.content_type import content_type
from .metrics import SendMessageMetrics
from .service import LineWorksService, ServiceNotReady

logger = logging.getLogger(__name__)

api = APIRouter()

TIMEOUT_ERRORS = (Timeout, urllib3.exceptions.TimeoutError, socket.timeout)


def get_service(request: Request) -> LineWorksService:
    service: LineWorksService = request.app.state.service
    return service


def parse_token(token: str) -> tuple[int, int]:
    try:
        to, channel_type = (int(i) for i in token.split(":"))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Bearer token must be '<channel_no>:<channel_type>'",
        )
    return to, channel_type


@api.post("/notify")
async def notify(
    request: Request,
    background_tasks: BackgroundTasks,
    service: LineWorksService = Depends(get_service),
    bearer_token: str = Depends(bearer_token),
    content_type: str = Depends(content_type),
) -> dict[str, str]:
    to, channel_type = parse_token(bearer_token)

    if content_type not in (
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    ):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type: {content_type or '(none)'}",
        )

    form = await request.form()
    message = form.get("message")
    sticker_id = form.get("stickerId")
    sticker_package_id = form.get("stickerPackageId")
    image_file = form.get("imageFile")

    try:
        if isinstance(message, str):
            with SendMessageMetrics(to, "text"):
                await service.call(lambda w: w.send_text_message(to, message))

        if isinstance(sticker_id, str) and isinstance(sticker_package_id, str):
            with SendMessageMetrics(to, "sticker"):
                sticker = service.sticker
                info = sticker.get_info(sticker_package_id) if sticker else None
                sticker_message = Sticker(
                    pkgId=sticker_package_id,
                    pkgVer=info["version"] if info else "",
                    stkId=sticker_id,
                    stkOpt="",
                    stkType="works" if info else "line",
                )
                await service.call(
                    lambda w: w.send_sticker_message(to, sticker_message)
                )

        if isinstance(image_file, UploadFile) and isinstance(image_file.filename, str):
            image_bytes = await image_file.read()
            file_name = image_file.filename
            with SendMessageMetrics(to, "image"):
                await service.call(
                    lambda w: w.send_image_message_with_file(
                        to, ChannelType(channel_type), image_bytes, file_name
                    )
                )
    except ServiceNotReady as e:
        raise HTTPException(
            status_code=503, detail=f"LINE WORKS client is not ready: {e}"
        )
    except TIMEOUT_ERRORS as e:
        logger.error(f"LINE WORKS request timed out: {e!r}")
        background_tasks.add_task(service.verify_session)
        raise HTTPException(
            status_code=504, detail=f"LINE WORKS request timed out: {e!r}"
        )
    except Exception as e:
        logger.error(f"LINE WORKS request failed: {e!r}", exc_info=e)
        background_tasks.add_task(service.verify_session)
        raise HTTPException(status_code=502, detail=f"LINE WORKS request failed: {e!r}")

    return {"status": "ok"}


@api.post("/reconnect")
async def reconnect(
    service: LineWorksService = Depends(get_service),
) -> dict[str, str]:
    service.request_reconnect("POST /api/reconnect")
    return {"status": "ok"}


__all__ = ["api", "get_service", "LineWorks"]
