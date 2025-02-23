import enum
import typing as t
from typing_extensions import Literal

from pydantic import BaseModel, Field

# XXX: Replace the non-commented-out code with what's commented out once nested
# types become a thing in mypy.
# JSONValue = t.Union[None, str, int,
#                     t.List['JSONValue'], t.Dict[str, 'JSONValue']]
# JSONDict = t.Dict[str, JSONValue]
JSONDict = t.Dict[str, t.Any]
JSONList = t.List[t.Any]

Id = t.Union[int, str]

ProgressToken = t.Union[int, str]


class Request(BaseModel):
    method: str
    id: t.Optional[Id] = None
    params: t.Optional[JSONDict] = None


class Response(BaseModel):
    id: t.Optional[Id] = None
    result: t.Optional[t.Union[t.List[t.Any], JSONDict]] = None
    error: t.Optional[JSONDict] = None


class MessageType(enum.IntEnum):
    ERROR = 1
    WARNING = 2
    INFO = 3
    LOG = 4
    DEBUG = 5


class MessageActionItem(BaseModel):
    title: str


class TextDocumentItem(BaseModel):
    uri: str
    languageId: str
    version: int
    text: str


class TextDocumentIdentifier(BaseModel):
    uri: str


class OptionalVersionedTextDocumentIdentifier(TextDocumentIdentifier):
    version: t.Optional[int]


class VersionedTextDocumentIdentifier(TextDocumentIdentifier):
    version: t.Optional[int]


# Sorting tip:  sorted(positions, key=(lambda p: p.as_tuple()))
class Position(BaseModel):
    # NB: These are both zero-based.
    line: int
    character: int

    def as_tuple(self) -> t.Tuple[int, int]:
        return (self.line, self.character)


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
    rangeLength: t.Optional[int]  # deprecated, use .range

    def model_dump(self, **kwargs: t.Any) -> t.Dict[str, t.Any]:
        d = super().model_dump(**kwargs)

        # vscode-css server requires un-filled values to be absent
        # TODO: add vscode-css to tests
        if self.rangeLength is None:
            del d["rangeLength"]
        if self.range is None:
            del d["range"]
        return d

    @classmethod
    def range_change(
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
        happened.
        """
        change_range = Range(start=change_start, end=change_end)
        return cls(
            range=change_range,
            rangeLength=change_range.calculate_length(old_text),
            text=change_text,
        )

    @classmethod
    def whole_document_change(
        cls, change_text: str
    ) -> "TextDocumentContentChangeEvent":
        return cls(text=change_text, range=None, rangeLength=None)


class TextDocumentPosition(BaseModel):
    textDocument: TextDocumentIdentifier
    position: Position


class CompletionTriggerKind(enum.IntEnum):
    INVOKED = 1
    TRIGGER_CHARACTER = 2
    TRIGGER_FOR_INCOMPLETE_COMPLETIONS = 3


class CompletionContext(BaseModel):
    triggerKind: CompletionTriggerKind
    triggerCharacter: t.Optional[str] = None


class MarkupKind(enum.Enum):
    PLAINTEXT = "plaintext"
    MARKDOWN = "markdown"


class MarkupContent(BaseModel):
    kind: MarkupKind
    value: str


class TextEdit(BaseModel):
    range: Range
    newText: str
    annotationId: t.Optional[str] = None


class TextDocumentEdit(BaseModel):
    textDocument: OptionalVersionedTextDocumentIdentifier
    edits: t.List[TextEdit]


class Command(BaseModel):
    title: str
    command: str
    arguments: t.Optional[t.List[t.Any]]


class InsertTextFormat(enum.IntEnum):
    PLAIN_TEXT = 1
    SNIPPET = 2


class CompletionItemKind(enum.IntEnum):
    TEXT = 1
    METHOD = 2
    FUNCTION = 3
    CONSTRUCTOR = 4
    FIELD = 5
    VARIABLE = 6
    CLASS = 7
    INTERFACE = 8
    MODULE = 9
    PROPERTY = 10
    UNIT = 11
    VALUE = 12
    ENUM = 13
    KEYWORD = 14
    SNIPPET = 15
    COLOR = 16
    FILE = 17
    REFERENCE = 18
    FOLDER = 19
    ENUMMEMBER = 20
    CONSTANT = 21
    STRUCT = 22
    EVENT = 23
    OPERATOR = 24
    TYPEPARAMETER = 25


class CompletionItemTag(enum.IntEnum):
    DEPRECATED = 1


class CompletionItem(BaseModel):
    label: str
    kind: t.Optional[CompletionItemKind] = None
    tags: t.Optional[CompletionItemTag] = None
    detail: t.Optional[str] = None
    documentation: t.Union[str, MarkupContent, None] = None
    deprecated: t.Optional[bool] = None
    preselect: t.Optional[bool] = None
    sortText: t.Optional[str] = None
    filterText: t.Optional[str] = None
    insertText: t.Optional[str] = None
    insertTextFormat: t.Optional[InsertTextFormat] = None
    textEdit: t.Optional[TextEdit] = None
    additionalTextEdits: t.Optional[t.List[TextEdit]] = None
    commitCharacters: t.Optional[t.List[str]] = None
    command: t.Optional[Command] = None
    data: t.Optional[t.Any] = None


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


class LocationLink(BaseModel):
    originSelectionRange: t.Optional[Range] = None
    targetUri: str  # in the spec the type is DocumentUri
    targetRange: Range
    targetSelectionRange: Range


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
    severity: t.Optional[DiagnosticSeverity] = None
    code: t.Optional[t.Union[int, str]] = None
    source: t.Optional[str] = None
    message: str
    relatedInformation: t.Optional[t.List[DiagnosticRelatedInformation]] = None


class MarkedString(BaseModel):
    language: str
    value: str


class ParameterInformation(BaseModel):
    label: t.Union[str, t.Tuple[int, int]]
    documentation: t.Optional[t.Union[str, MarkupContent]] = None


class SignatureInformation(BaseModel):
    label: str
    documentation: t.Optional[t.Union[MarkupContent, str]] = None
    parameters: t.Optional[t.List[ParameterInformation]] = None
    activeParameter: t.Optional[int] = None


class SymbolKind(enum.IntEnum):
    FILE = 1
    MODULE = 2
    NAMESPACE = 3
    PACKAGE = 4
    CLASS = 5
    METHOD = 6
    PROPERTY = 7
    FIELD = 8
    CONSTRUCTOR = 9
    ENUM = 10
    INTERFACE = 11
    FUNCTION = 12
    VARIABLE = 13
    CONSTANT = 14
    STRING = 15
    NUMBER = 16
    BOOLEAN = 17
    ARRAY = 18
    OBJECT = 19
    KEY = 20
    NULL = 21
    ENUMMEMBER = 22
    STRUCT = 23
    EVENT = 24
    OPERATOR = 25
    TYPEPARAMETER = 26


class SymbolTag(enum.IntEnum):
    DEPRECATED = 1


class CallHierarchyItem(BaseModel):
    name: str
    kind: SymbolKind
    tags: t.Optional[SymbolTag] = None
    detail: t.Optional[str] = None
    uri: str
    range: Range
    selectionRange: Range
    data: t.Optional[t.Any] = None


class CallHierarchyIncomingCall(BaseModel):
    from_: CallHierarchyItem = Field(alias="from")
    fromRanges: t.List[Range]


class CallHierarchyOutgoingCall(BaseModel):
    to: CallHierarchyItem
    fromRanges: t.List[Range]


class TextDocumentSyncKind(enum.IntEnum):
    NONE = 0
    FULL = 1
    INCREMENTAL = 2


# Usually in a flat list
class SymbolInformation(BaseModel):
    name: str
    kind: SymbolKind
    tags: t.Optional[t.List[SymbolTag]] = None
    deprecated: t.Optional[bool] = None
    location: Location
    containerName: t.Optional[str] = None


class InlayHintLabelPart(BaseModel):
    value: str
    tooltip: t.Optional[t.Union[str, MarkupContent]]
    location: t.Optional[Location] = None
    command: t.Optional[Command] = None


class InlayHintKind(enum.IntEnum):
    TYPE = 1
    PARAMETER = 2


class InlayHint(BaseModel):
    position: Position
    label: t.Union[str, t.List[InlayHintLabelPart]]
    kind: t.Optional[InlayHintKind] = None
    textEdits: t.Optional[t.List[TextEdit]]
    tooltip: t.Optional[t.Union[str, MarkupContent]]
    paddingLeft: t.Optional[bool] = None
    paddingRight: t.Optional[bool] = None
    data: t.Optional[t.Any] = None


class FoldingRange(BaseModel):
    startLine: int
    startCharacter: t.Optional[int] = None
    endLine: int
    endCharacter: t.Optional[int] = None
    kind: t.Optional[str] = None  # comment, imports, region
    collapsedText: t.Optional[str] = None


# Usually a hierarchy, e.g. a symbol with kind=SymbolKind.CLASS contains
# several SymbolKind.METHOD symbols
class DocumentSymbol(BaseModel):
    name: str
    detail: t.Optional[str] = None
    kind: SymbolKind
    tags: t.Optional[t.List[SymbolTag]] = None
    deprecated: t.Optional[bool] = None
    range: Range = Field(..., validate_default=True)
    selectionRange: Range = Field(
        ..., validate_default=True
    )  # Example: symbol.selectionRange.start.as_tuple()
    # https://stackoverflow.com/questions/36193540
    children: t.Optional[t.List["DocumentSymbol"]] = None


# for `.children` treeness
DocumentSymbol.model_rebuild()


class Registration(BaseModel):
    id: str
    method: str
    registerOptions: t.Optional[t.Any] = None


class FormattingOptions(BaseModel):
    tabSize: int
    insertSpaces: bool
    trimTrailingWhitespace: t.Optional[bool] = None
    insertFinalNewline: t.Optional[bool] = None
    trimFinalNewlines: t.Optional[bool] = None


class WorkspaceFolder(BaseModel):
    uri: str
    name: str


class ProgressValue(BaseModel):
    pass


class WorkDoneProgressValue(ProgressValue):
    pass


class MWorkDoneProgressKind(enum.Enum):
    BEGIN = "begin"
    REPORT = "report"
    END = "end"


class WorkDoneProgressBeginValue(WorkDoneProgressValue):
    kind: Literal["begin"]
    title: str
    cancellable: t.Optional[bool] = None
    message: t.Optional[str] = None
    percentage: t.Optional[int] = None


class WorkDoneProgressReportValue(WorkDoneProgressValue):
    kind: Literal["report"]
    cancellable: t.Optional[bool] = None
    message: t.Optional[str] = None
    percentage: t.Optional[int] = None


class WorkDoneProgressEndValue(WorkDoneProgressValue):
    kind: Literal["end"]
    message: t.Optional[str] = None


class ConfigurationItem(BaseModel):
    scopeUri: t.Optional[str] = None
    section: t.Optional[str] = None
