from fastapi import APIRouter, Depends, Request
from line_works.client import ChannelType, LineWorks, Sticker
from starlette.datastructures import UploadFile

from .depends.bearer import bearer_token
from .depends.content_type import content_type
from .depends.line_sticker import LineWorksSticker, line_works_sticker_depends
from .depends.line_works import line_works_depends

api = APIRouter()


@api.post("/notify")
async def notify(
    request: Request,
    works: LineWorks = Depends(line_works_depends),
    bearer_token: str = Depends(bearer_token),
    content_type: str = Depends(content_type),
    sticker: LineWorksSticker = Depends(line_works_sticker_depends),
):
    to, channel_type = [int(i) for i in bearer_token.split(":")]

    if content_type == "application/x-www-form-urlencoded":
        form = await request.form()
        message = form.get("message")
        sticker_id = form.get("stickerId")
        sticker_package_id = form.get("stickerPackageId")
        if isinstance(message, str):
            works.send_text_message(
                to,
                message,
            )
        if isinstance(sticker_id, str) and isinstance(sticker_package_id, str):
            info = sticker.get_info(sticker_package_id)
            works.send_sticker_message(
                to,
                Sticker(
                    pkgId=sticker_package_id,
                    pkgVer=info["version"] if info else "",
                    stkId=sticker_id,
                    stkOpt="",
                    stkType="works" if info else "line",
                ),
            )
    elif content_type == "multipart/form-data":
        form = await request.form()
        message = form.get("message")
        imageFile = form.get("imageFile")
        if isinstance(message, str):
            works.send_text_message(
                to,
                message,
            )
        if isinstance(imageFile, UploadFile) and isinstance(imageFile.filename, str):
            works.send_image_message_with_file(
                to,
                ChannelType(channel_type),
                imageFile.file.read(),
                imageFile.filename,
            )

    return {"status": "ok"}
