import enum
import typing as t

from attr import attrs, attrib

# XXX: Temporarily disabled this type annotation until I get json schemas.
# JSONValue = t.Union[None, str, int, t.List[t.Any], t.Dict[str, t.Any]]
# JSONDict = t.Dict[str, JSONValue]
JSONDict = t.Dict[str, t.Any]


@attrs
class Request:
    id: int = attrib()
    method: str = attrib()
    params: t.Optional[JSONDict] = attrib()


@attrs
class Response:
    id: int = attrib()
    result: t.Optional[JSONDict] = attrib(default=None)
    error: t.Optional[JSONDict] = attrib(default=None)


class MessageType(enum.IntEnum):
    ERROR = 1
    WARNING = 2
    INFO = 3
    LOG = 4


@attrs
class MessageActionItem:
    title: str = attrib()
