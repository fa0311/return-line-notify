import logging
import os
from logging import StreamHandler
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def init_logger(path: Path) -> None:
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
