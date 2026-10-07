import json
import re
from typing import Optional

from line_works.client import LineWorks
from line_works.config import HEADERS

_SCRIPT_RE = re.compile(r"<script>(.*?)</script>", re.DOTALL)
_TRY_CATCH_RE = re.compile(r"try{(.*?)}catch\(e\){ console\.error\(e\)}", re.DOTALL)


class LineWorksSticker:
    def __init__(self, sticker: dict) -> None:
        self.sticker = sticker

    def get_info(self, pkg_id: str) -> Optional[dict]:
        packages = self.sticker.get("stickerPackages", [])
        res = [sticker for sticker in packages if sticker["id"] == pkg_id]
        return res[0] if len(res) > 0 else None


def load_sticker_config(works: LineWorks) -> LineWorksSticker:
    """トーク画面の HTML に埋め込まれたスタンプ設定を取り出す (同期 HTTP)"""
    url = "https://talk.worksmobile.com/#/"
    res = works.session.get(url, headers=HEADERS)
    res.raise_for_status()

    variable: dict[str, object] = {}
    for script in _SCRIPT_RE.findall(res.text):
        for value in _TRY_CATCH_RE.findall(script):
            key, value = value.split("=", 1)
            variable[key.strip()] = json.loads(value.strip())
    preload = variable["window['preloadOnPageLoad']"]
    assert isinstance(preload, dict)
    return LineWorksSticker(json.loads(preload["sticker_config"]))
