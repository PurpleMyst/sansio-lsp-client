import typing as t

from pydantic import BaseModel, PrivateAttr

if t.TYPE_CHECKING:  # avoid import cycle at runtime
    from .client import Client
from .structs import (
    FoldingRange,
    JSONDict,
    Diagnostic,
    MessageType,
    MessageActionItem,
    CompletionList,
    TextEdit,
    TextDocumentEdit,
    MarkupContent,
    Range,
    Location,
    MarkedString,
    SignatureInformation,
    LocationLink,
    CallHierarchyItem,
    SymbolInformation,
    Registration,
    DocumentSymbol,
    WorkspaceFolder,
    ProgressToken,
    ProgressValue,
    WorkDoneProgressBeginValue,
    WorkDoneProgressReportValue,
    WorkDoneProgressEndValue,
    ConfigurationItem,
)

Id = t.Union[int, str]


class Event(BaseModel):
    pass


class ResponseError(Event):
    message_id: t.Optional[Id]
    code: int
    message: str
    data: t.Optional[t.Union[str, int, float, bool, t.List[t.Any], JSONDict, None]]


class ServerRequest(Event):
    _client: "Client" = PrivateAttr()
    _id: Id = PrivateAttr()


class ServerNotification(Event):
    pass


class Initialized(Event):
    capabilities: JSONDict


class Shutdown(Event):
    pass


class ShowMessage(ServerNotification):
    type: MessageType
    message: str


class ShowMessageRequest(ServerRequest):
    type: MessageType
    message: str
    actions: t.Optional[t.List[MessageActionItem]]

    def reply(self, action: t.Optional[MessageActionItem] = None) -> None:
        """
        Reply to the ShowMessageRequest with the user's selection.

        No bytes are actually returned from this method, the reply's bytes
        are added to the client's internal send buffer.
        """
        self._client._send_response(
            id=self._id, result=action.dict() if action is not None else None
        )


class LogMessage(ServerNotification):
    type: MessageType
    message: str


class WorkDoneProgressCreate(ServerRequest):
    token: ProgressToken

    def reply(self) -> None:
        self._client._send_response(id=self._id, result=None)


class Progress(ServerNotification):
    token: ProgressToken
    value: ProgressValue


class WorkDoneProgress(Progress):
    pass


class WorkDoneProgressBegin(WorkDoneProgress):
    value: WorkDoneProgressBeginValue


class WorkDoneProgressReport(WorkDoneProgress):
    value: WorkDoneProgressReportValue


class WorkDoneProgressEnd(WorkDoneProgress):
    value: WorkDoneProgressEndValue


# XXX: should these two be just Events or?
class Completion(Event):
    message_id: Id
    completion_list: t.Optional[CompletionList]


# XXX: not sure how to name this event.
class WillSaveWaitUntilEdits(Event):
    edits: t.Optional[t.List[TextEdit]]


class PublishDiagnostics(ServerNotification):
    uri: str
    diagnostics: t.List[Diagnostic]


class Hover(Event):
    message_id: t.Optional[Id]  # custom...
    contents: t.Union[
        t.List[t.Union[MarkedString, str]], MarkedString, MarkupContent, str
    ]
    range: t.Optional[Range]


class SignatureHelp(Event):
    message_id: t.Optional[Id]  # custom...
    signatures: t.List[SignatureInformation]
    activeSignature: t.Optional[int]
    activeParameter: t.Optional[int]

    def get_hint_str(self) -> t.Optional[str]:
        if len(self.signatures) == 0:
            return None
        active_sig = self.activeSignature or 0
        sig = self.signatures[active_sig]
        return sig.label


class Definition(Event):
    message_id: t.Optional[Id]
    result: t.Union[Location, t.List[t.Union[Location, LocationLink]], None]

class WorkspaceEdit(Event):
    message_id: t.Optional[Id]
    changes: t.Optional[t.Dict[str, TextEdit]]
    documentChanges: t.Optional[t.List[TextDocumentEdit]]

# result is a list, so putting in a custom class
class References(Event):
    result: t.Union[t.List[Location], None]


class MCallHierarchItems(Event):
    result: t.Union[t.List[CallHierarchyItem], None]


class Implementation(Event):
    result: t.Union[Location, t.List[t.Union[Location, LocationLink]], None]


class MWorkspaceSymbols(Event):
    result: t.Union[t.List[SymbolInformation], None]

class MFoldingRanges(Event):
    message_id: t.Optional[Id]
    result: t.Optional[t.List[FoldingRange]]

class MDocumentSymbols(Event):
    message_id: t.Optional[Id]
    result: t.Union[t.List[SymbolInformation], t.List[DocumentSymbol], None]


class Declaration(Event):
    result: t.Union[Location, t.List[t.Union[Location, LocationLink]], None]


class TypeDefinition(Event):
    result: t.Union[Location, t.List[t.Union[Location, LocationLink]], None]


class RegisterCapabilityRequest(ServerRequest):
    registrations: t.List[Registration]

    def reply(self) -> None:
        self._client._send_response(id=self._id, result={})

class DocumentFormatting(Event):
    message_id: t.Optional[Id]
    result: t.Union[t.List[TextEdit], None]

class WorkspaceFolders(ServerRequest):
    result: t.Optional[t.List[WorkspaceFolder]]

    def reply(self, folders: t.Optional[t.List[WorkspaceFolder]] = None) -> None:
        """
        Reply to the WorkspaceFolder with workspace folders.

        No bytes are actually returned from this method, the reply's bytes
        are added to the client's internal send buffer.
        """
        self._client._send_response(
            id=self._id,
            result=[f.dict() for f in folders] if folders is not None else None,
        )


class ConfigurationRequest(ServerRequest):
    items: t.List[ConfigurationItem]

    def reply(self, result: t.List[t.Any] = []) -> None:
        self._client._send_response(id=self._id, result=result)
