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
    # NEW ########
    MarkedString,
    ParameterInformation,
    SignatureInformation,
    LocationLink,
    CallHierarchyItem,
    SymbolInformation,
    Registration,
    DocumentSymbol,
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


# NEW ##################
""" Hover:
    * contents: MarkedString | MarkedString[] | MarkupContent;
    * range?: Range;
"""
class Hover(Event):
    message_id: t.Optional[Id] # custom...
    contents: t.Union[
            t.List[t.Union[MarkedString, str]],
            MarkedString, # .language, .value
            MarkupContent, # kind: MarkupKind, value: str
            str,
            ]
    range: t.Optional[Range]

    # DBG
    def m_str(self):
        def item_str(item): #SKIP
            if isinstance(item, MarkedString):
                return f'[{item.language}]\n{item.value}'
            elif isinstance(item, MarkupContent):
                return f'[{item.kind}]\n{item.value}'
            return item # str

        if isinstance(self.contents, list):
            return '\n'.join((item_str(item) for item in self.contents))
        return item_str(self.contents)

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
        params = sig.parameters
        #  names of params if all strings
        if (params
                and  len(params) > 0
                and  all(isinstance(param.label, str)  for param in params)):
            return ', '.join((param.label for param in params))
        # ... or just label of signature
        else:
            return sig.label


class Definition(Event):
    result: t.Union[
        Location,
        t.List[t.Union[Location, LocationLink]],
        None]

# result is a list, so putting i a custom class
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


