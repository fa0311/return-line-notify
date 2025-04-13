import json
import re
from typing import Optional

from line_works.client import LineWorks
from line_works.config import HEADERS


class LineWorksStickerFixture:
    def __init__(self):
        pass

    def init(self, works: LineWorks):
        url = "https://talk.worksmobile.com/#/"
        res = works.session.get(url, headers=HEADERS)

        script_reg = re.compile(r"<script>(.*?)</script>")
        script_tag = script_reg.findall(res.text)
        try_catch_re = re.compile(r"try{(.*?)}catch\(e\){ console\.error\(e\)}")
        try_catch_list = [try_catch_re.findall(script) for script in script_tag]
        variable = {}
        for try_catch in try_catch_list:
            for value in try_catch:
                assert isinstance(value, str)
                key, value = value.split("=", 1)
                variable[key.strip()] = json.loads(value.strip())
        preload = variable["window['preloadOnPageLoad']"]
        self.sticker = json.loads(preload["sticker_config"])

    def __call__(self):
        return LineWorksSticker(self.sticker)


class LineWorksSticker:
    def __init__(self, sticker: dict):
        self.sticker = sticker

    def get_info(self, pkg_id: str) -> Optional[dict]:
        packages = self.sticker["stickerPackages"]
        res = [sticker for sticker in packages if sticker["id"] == pkg_id]
        return res[0] if len(res) > 0 else None


line_works_sticker_depends = LineWorksStickerFixture()
