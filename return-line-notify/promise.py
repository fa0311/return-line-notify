import asyncio
from typing import Generic, TypeVar

T = TypeVar("T")


class Promise(Generic[T]):
    _future: asyncio.Future[T]

    def __init__(self):
        loop = asyncio.get_event_loop()
        self._future = loop.create_future()

    def resolve(self, value: T):
        if not self._future.done():
            self._future.set_result(value)

    def reject(self, error: Exception):
        if not self._future.done():
            self._future.set_exception(error)

    def __call__(self):
        return self._future
