from .depends.line_reconnect import line_reconnect_depends


async def reconnect():
    await line_reconnect_depends()()
    raise ReconnectError("Reconnecting to Line Works")


class ReconnectError(Exception):
    pass
