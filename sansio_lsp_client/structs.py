import enum
import typing as t

from pydantic import BaseModel

# XXX: Replace the non-commented-out code with what's commented out once nested
# types become a thing in mypy.
# JSONValue = t.Union[None, str, int,
#                     t.List['JSONValue'], t.Dict[str, 'JSONValue']]
# JSONDict = t.Dict[str, JSONValue]
JSONDict = t.Dict[str, t.Any]

Id = t.Union[int, str]


class Request(BaseModel):
    method: str
    id: t.Optional[Id]
    params: t.Optional[JSONDict]


class Response(BaseModel):
    id: t.Optional[Id]
    result: t.Optional[JSONDict]
    error: t.Optional[JSONDict]


class MessageType(enum.IntEnum):
    ERROR = 1
    WARNING = 2
    INFO = 3
    LOG = 4


class MessageActionItem(BaseModel):
    title: str


class TextDocumentItem(BaseModel):
    uri: str
    languageId: str
    version: int
    text: str


class TextDocumentIdentifier(BaseModel):
    uri: str


class VersionedTextDocumentIdentifier(TextDocumentIdentifier):
    version: t.Optional[int]


class Position(BaseModel):
    # NB: These are both zero-based.
    line: int
    character: int


class Range(BaseModel):
    start: Position
    end: Position

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


class TextDocumentContentChangeEvent(BaseModel):
    text: str
    range: t.Optional[Range]
    rangeLength: t.Optional[int]

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

        Nota bene: If you're creating a list of
        TextDocumentContentChangeEvent based on many changes, `old_text` must
        reflect the state of the text after all previous change events
        happened. Or you can just use
        `sansio_lsp_client.utils.calculate_change_events`.
        """
        change_range = Range(start=change_start, end=change_end)
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


class TextDocumentPosition(BaseModel):
    textDocument: TextDocumentIdentifier
    position: Position


class CompletionTriggerKind(enum.IntEnum):
    INVOKED = 1
    TRIGGER_CHARACTER = 2
    TRIGGER_FOR_INCOMPLETE_COMPLETIONS = 3


class CompletionContext(BaseModel):
    triggerKind: CompletionTriggerKind
    triggerCharacter: t.Optional[str]


class MarkupKind(enum.Enum):
    PLAINTEXT = "plaintext"
    MARKDOWN = "markdown"


class MarkupContent(BaseModel):
    kind: MarkupKind
    value: str


class TextEdit(BaseModel):
    range: Range
    newText: str


class Command(BaseModel):
    title: str
    command: str
    arguments: t.Optional[t.List[t.Any]]


class InsertTextFormat(enum.IntEnum):
    PLAIN_TEXT = 1
    SNIPPET = 2


class CompletionItem(BaseModel):
    label: str
    # TODO: implement CompletionItemKind.
    kind: t.Optional[int]
    detail: t.Optional[str]
    # FIXME: Allow `t.Union[str, MarkupContent]` here
    documentation: t.Optional[str]
    deprecated: t.Optional[bool]
    preselect: t.Optional[bool]
    sortText: t.Optional[str]
    filterText: t.Optional[str]
    insertText: t.Optional[str]
    insertTextFormat: t.Optional[InsertTextFormat]
    textEdit: t.Optional[TextEdit]
    additionalTextEdits: t.Optional[t.List[TextEdit]]
    commitCharacters: t.Optional[t.List[str]]
    command: t.Optional[Command]
    data: t.Optional[t.Any]


class CompletionList(BaseModel):
    isIncomplete: bool
    items: t.List[CompletionItem]


class TextDocumentSaveReason(enum.IntEnum):
    MANUAL = 1
    AFTER_DELAY = 2
    FOCUS_OUT = 3


class Location(BaseModel):
    uri: str
    range: Range


class DiagnosticRelatedInformation(BaseModel):
    location: Location
    message: str


class DiagnosticSeverity(enum.IntEnum):
    ERROR = 1
    WARNING = 2
    INFORMATION = 3
    HINT = 4


class Diagnostic(BaseModel):
    range: Range

    # TODO: Make this a proper enum
    # XXX: ^ Is this comment still relevant?
    severity: DiagnosticSeverity

    # TODO: Support this as an union of str and int
    code: t.Optional[t.Any]

    source: t.Optional[str]

    message: t.Optional[str]

    relatedInformation: t.Optional[t.List[DiagnosticRelatedInformation]]
