import logging
import os
from logging import StreamHandler
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# アクセスログに出さないパス (監視系のポーリングでログが埋まるのを防ぐ)
QUIET_PATHS = ("/health", "/metrics")


class AccessLogFilter(logging.Filter):
    """uvicorn のアクセスログから監視系のリクエストを落とす"""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3:
            path = args[2]
            if isinstance(path, str) and path.startswith(QUIET_PATHS):
                return False
        return True


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
    logging.getLogger("uvicorn.access").addFilter(AccessLogFilter())
    # websockets は DEBUG でハンドシェイクのヘッダ (Cookie 込み) を出すので抑止
    logging.getLogger("websockets").setLevel(logging.INFO)
