from typing import TypeVar

from ..promise import Promise

T = TypeVar("T")


class LineReconnectFixture:
    def __init__(self):
        pass

    def init(self, promise: Promise[None]):
        self.__promise = promise

    def __call__(self):
        return self.__promise


line_reconnect_depends = LineReconnectFixture()
