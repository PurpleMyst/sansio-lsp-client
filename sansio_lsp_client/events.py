import typing as t

from pydantic import BaseModel, PrivateAttr

if t.TYPE_CHECKING:  # avoid import cycle at runtime
    from .client import Client
from .structs import (
    JSONDict,
    Diagnostic,
    MessageType,
    MessageActionItem,
    CompletionItem,
    CompletionList,
    TextEdit,
    MarkupContent,
    Range,
    Location,
    MarkedString,
    ParameterInformation,
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

# for type checking
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


<<<<<<< HEAD
=======
""" Hover:
    * contents: MarkedString | MarkedString[] | MarkupContent;
    * range?: Range;
"""
>>>>>>> 5181466d0c26d826f45b60e6c41343ccc1e11746
class Hover(Event):
    message_id: t.Optional[Id] # custom...
    contents: t.Union[
            t.List[t.Union[MarkedString, str]],
            MarkedString, # .language, .value
            MarkupContent, # kind: MarkupKind, value: str
            str,
            ]
    range: t.Optional[Range]


class SignatureHelp(Event):
    message_id: t.Optional[Id] # custom...
    signatures: t.List[SignatureInformation]
    activeSignature: t.Optional[int]
    activeParameter: t.Optional[int]

    def get_hint_str(self):
        if len(self.signatures) == 0:
            return None
        active_sig = self.activeSignature or 0
        sig = self.signatures[active_sig]
        return sig.label


class Definition(Event):
    result: t.Union[
        Location,
        t.List[t.Union[Location, LocationLink]],
        None]


class References(Event):
    result: t.List[Location]


class MCallHierarchItems(Event):
    result: t.Union[t.List[CallHierarchyItem], None]


class Implementation(Event):
    result: t.Union[
        Location,
        t.List[t.Union[Location, LocationLink]],
        None]


class MWorkspaceSymbols(Event):
    result: t.Union[t.List[SymbolInformation], None]


class MDocumentSymbols(Event):
    result: t.Union[t.List[SymbolInformation], t.List[DocumentSymbol], None]


class Declaration(Event):
    result: t.Union[
        Location,
        t.List[t.Union[Location, LocationLink]],
        None]


class TypeDefinition(Event):
    result: t.Union[
        Location,
        t.List[t.Union[Location, LocationLink]],
        None]


class RegisterCapabilityRequest(ServerRequest):
    registrations: t.List[Registration]

    def reply(self) -> None:
        self._client._send_response(id=self._id, result={})


class DocumentFormatting(Event):
    message_id: t.Optional[Id] # custom...
    result: t.Union[t.List[TextEdit], None]


class WorkspaceFolders(ServerRequest):
    result: None

    def reply(self, folders: t.Optional[t.List[WorkspaceFolder]] = None) -> None:
        """
        Reply to the WorkspaceFolder with workspace folders.

        No bytes are actually returned from this method, the reply's bytes
        are added to the client's internal send buffer.
        """
        self._client._send_response(
            id=self._id, result=[f.dict() for f in folders] if folders is not None else None
        )


class ConfigurationRequest(ServerRequest):
    items: t.List[ConfigurationItem]

    def reply(self, result=t.List[t.Any]) -> None:
        self._client._send_response(id=self._id,  result=result)
