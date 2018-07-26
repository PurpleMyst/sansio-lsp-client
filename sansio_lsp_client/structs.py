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


@attrs
class TextDocumentItem:
    uri: str = attrib()
    languageId: str = attrib()
    version: int = attrib()
    text: str = attrib()


@attrs
class TextDocumentIdentifier:
    uri: str = attrib()


@attrs
class VersionedTextDocumentIdentifier(TextDocumentIdentifier):
    version: t.Optional[int] = attrib()


@attrs
class Position:
    line: int = attrib()
    character: int = attrib()


@attrs
class Range:
    start: Position = attrib()
    end: Position = attrib()


@attrs
class TextDocumentContentChangeEvent:
    range: t.Optional[Range] = attrib()
    rangeLength: t.Optional[int] = attrib()
    text: str = attrib()

    # XXX: This is a weird method name.
    @classmethod
    def from_python(
        cls, change_start: int, change_end: int, change_text: str
    ) -> "TextDocumentContentChangeEvent":
        return cls(
            range=Range(change_start, change_end),
            rangeLength=change_end - change_start,
            text=change_text,
        )
