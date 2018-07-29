import enum
import typing as t

from attr import attrs, attrib

# XXX: Replace the non-commented-out code with what's commented out once nested
# types become a thing in mypy.
# JSONValue = t.Union[None, str, int, t.List['JSONValue'], t.Dict[str, 'JSONValue']]
# JSONDict = t.Dict[str, JSONValue]
JSONDict = t.Dict[str, t.Any]

# XXX: We can't have this be both str and int due to `cattrs` restrictions. How
# can we fix this?
# Id = t.Union[str, int]
Id = int


@attrs
class Request:
    method: str = attrib()
    id: t.Optional[Id] = attrib(default=None)
    params: t.Optional[JSONDict] = attrib(default=None)


@attrs
class Response:
    id: t.Optional[Id] = attrib(default=None)
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
    version: t.Optional[int] = attrib(default=None)


@attrs
class Position:
    # NB: These are both zero-based.
    line: int = attrib()
    character: int = attrib()


@attrs
class Range:
    start: Position = attrib()
    end: Position = attrib()

    def calculate_length(self, text: str) -> int:
        text_lines = text.splitlines()

        if self.end.line == self.start.line:
            line = text_lines[self.start.line]
            return len(line[self.start.character : self.end.character])
        else:
            total = 0

            total += len(text_lines[self.start.line][self.start.character :])

            for line_number in range(self.start.line + 1, self.end.line):
                total += len(text_lines[line_number])

            total += len(text_lines[self.end.line][: self.end.character])

            return total


@attrs
class TextDocumentContentChangeEvent:
    text: str = attrib()
    range: t.Optional[Range] = attrib(default=None)
    rangeLength: t.Optional[int] = attrib(default=None)

    @classmethod
    def change_range(
        cls,
        change_start: Position,
        change_end: Position,
        change_text: str,
        old_text: str,
    ) -> "TextDocumentContentChangeEvent":
        """
        Create a TextDocumentContentChangeEvent reflecting the given changes.

        Nota bene: If you're creating a list of TextDocumentContentChangeEvent based on many changes,
        `old_text` must reflect the state of the text after all previous change events happened.
        Or you can just use `sansio_lsp_client.utils.calculate_change_events`.
        """
        change_range = Range(change_start, change_end)
        return cls(
            range=change_range,
            rangeLength=change_range.calculate_length(old_text),
            text=change_text,
        )

    @classmethod
    def change_whole_document(
        cls, change_text: str
    ) -> "TextDocumentContentChangeEvent":
        return cls(text=change_text)


@attrs
class TextDocumentPosition:
    textDocument: TextDocumentIdentifier = attrib()
    position: Position = attrib()


class CompletionTriggerKind(enum.IntEnum):
    INVOKED = 1
    TRIGGER_CHARACTER = 2
    TRIGGER_FOR_INCOMPLETE_COMPLETIONS = 3


@attrs
class CompletionContext:
    triggerKind: CompletionTriggerKind = attrib()
    triggerCharacter: t.Optional[str] = attrib(default=None)


class MarkupKind(enum.Enum):
    PLAINTEXT = "plaintext"
    MARKDOWN = "markdown"


@attrs
class MarkupContent:
    kind: MarkupKind = attrib()
    value: str = attrib()


@attrs
class TextEdit:
    range: Range = attrib()
    newText: str = attrib()


@attrs
class Command:
    title: str = attrib()
    command: str = attrib()
    arguments: t.Optional[t.List[t.Any]] = attrib(default=None)


class InsertTextFormat(enum.IntEnum):
    PLAIN_TEXT = 1
    SNIPPET = 2


@attrs
class CompletionItem:
    label: str = attrib()
    # TODO: implement CompletionItemKind.
    kind: t.Optional[int] = attrib(default=None)
    detail: t.Optional[str] = attrib(default=None)
    # FIXME: Allow `t.Union[str, MarkupContent]` here by defining a cattrs
    # custom loads hook.
    documentation: t.Optional[str] = attrib(default=None)
    deprecated: t.Optional[bool] = attrib(default=None)
    preselect: t.Optional[bool] = attrib(default=None)
    sortText: t.Optional[str] = attrib(default=None)
    filterText: t.Optional[str] = attrib(default=None)
    insertText: t.Optional[str] = attrib(default=None)
    insertTextFormat: t.Optional[InsertTextFormat] = attrib(default=None)
    textEdit: t.Optional[TextEdit] = attrib(default=None)
    additionalTextEdits: t.Optional[t.List[TextEdit]] = attrib(default=None)
    commitCharacters: t.Optional[t.List[str]] = attrib(default=None)
    command: t.Optional[Command] = attrib(default=None)
    data: t.Optional[t.Any] = attrib(default=None)


@attrs
class CompletionList:
    isIncomplete: bool = attrib()
    items: t.List[CompletionItem] = attrib()


class TextDocumentSaveReason(enum.IntEnum):
    MANUAL = 1
    AFTER_DELAY = 2
    FOCUS_OUT = 3
