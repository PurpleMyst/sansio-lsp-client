import enum
import typing as t
import logging

from pydantic import parse_obj_as, ValidationError

from .events import (
    ResponseError,
    Initialized,
    Completion,
    ServerRequest,
    Shutdown,
    PublishDiagnostics,
    Event,
    ShowMessage,
    ServerNotification,
    WillSaveWaitUntilEdits,
    ShowMessageRequest,
    LogMessage,
    Hover,
    SignatureHelp,
    Definition,
    References,
    MCallHierarchItems,
    Implementation,
    MWorkspaceSymbols,
    Declaration,
    TypeDefinition,
    RegisterCapabilityRequest,
    MDocumentSymbols,
    DocumentFormatting,
    Progress,
    WorkDoneProgress,
    WorkDoneProgressCreate,
    WorkDoneProgressBegin,
    WorkDoneProgressReport,
    WorkDoneProgressEnd,
    ConfigurationRequest,
    WorkspaceFolders,
)
from .structs import (
    Response,
    TextDocumentPosition,
    CompletionContext,
    CompletionList,
    CompletionItemKind,
    CompletionItem,
    Request,
    JSONDict,
    TextDocumentItem,
    TextDocumentIdentifier,
    VersionedTextDocumentIdentifier,
    TextDocumentContentChangeEvent,
    TextDocumentSaveReason,
    TextEdit,
    Id,
    SymbolKind,
    FormattingOptions,
    Range,
    WorkspaceFolder,
    ProgressToken,
    MWorkDoneProgressKind,
)
from .io_handler import _make_request, _parse_messages, _make_response

logger = logging.getLogger(__name__)


class ClientState(enum.Enum):
    NOT_INITIALIZED = enum.auto()
    WAITING_FOR_INITIALIZED = enum.auto()
    NORMAL = enum.auto()
    WAITING_FOR_SHUTDOWN = enum.auto()
    SHUTDOWN = enum.auto()
    EXITED = enum.auto()


CAPABILITIES = {
    "textDocument": {
        "synchronization": {
            "didSave": True,
            #'willSaveWaitUntil': True,
            "dynamicRegistration": True,
            #'willSave': True
        },
        "publishDiagnostics": {"relatedInformation": True},
        "completion": {
            "dynamicRegistration": True,
            "completionItem": {"snippetSupport": False},
            "completionItemKind": {"valueSet": list(CompletionItemKind)},
        },
        "hover": {
            "dynamicRegistration": True,
            "contentFormat": ["markdown", "plaintext"],
        },
        "definition": {"dynamicRegistration": True, "linkSupport": True},
        "signatureHelp": {
            "dynamicRegistration": True,
            "signatureInformation": {
                "parameterInformation": {
                    "labelOffsetSupport": False  # substring from label
                },
                "documentationFormat": ["markdown", "plaintext"],
            },
        },
        "implementation": {"linkSupport": True, "dynamicRegistration": True},
        "references": {"dynamicRegistration": True},
        "callHierarchy": {"dynamicRegistration": True},
        "declaration": {"linkSupport": True, "dynamicRegistration": True},
        "typeDefinition": {"linkSupport": True, "dynamicRegistration": True},
        "formatting": {"dynamicRegistration": True},
        "rangeFormatting": {"dynamicRegistration": True},
        "documentSymbol": {
            "hierarchicalDocumentSymbolSupport": True,
            "dynamicRegistration": True,
            "symbolKind": {"valueSet": list(SymbolKind)},
        },
    },
    "window": {
        "showMessage": {
            # TODO 'messageActionItem':...
        },
        "workDoneProgress": True,
    },
    "workspace": {
        "symbol": {
            "dynamicRegistration": True,
            "symbolKind": {"valueSet": list(SymbolKind)},
        },
        "workspaceFolders": True,
        # TODO 'workspaceEdit':..., #'applyEdit':..., 'executeCommand':...,
        "configuration": True,
        "didChangeConfiguration": {"dynamicRegistration": True},
    },
}


class Client:
    # TODO: Save the encoding given here.
    def __init__(
        self,
        process_id: t.Optional[int] = None,
        root_uri: t.Optional[str] = None,
        workspace_folders: t.Optional[t.List[WorkspaceFolder]] = None,
        trace: str = "off",
    ) -> None:
        self._state = ClientState.NOT_INITIALIZED

        # Used to save data as it comes in (from `recieve_bytes`) until we have
        # a full request.
        self._recv_buf = bytearray()

        # Things that we still need to send.
        self._send_buf = bytearray()

        # Keeps track of which IDs match to which unanswered requests.
        self._unanswered_requests: t.Dict[Id, Request] = {}

        # Just a simple counter to make sure we have unique IDs. We could make
        # sure that this fits into a JSONRPC Number, seeing as Python supports
        # bignums, but I think that's an unlikely enough case that checking for
        # it would just litter the code unnecessarily.
        self._id_counter = 0

        # Store type of '$/progress' for parsing
        self._progress_tokens_map: t.Dict[ProgressToken, t.Type[Progress]] = {}

        # We'll just immediately send off an "initialize" request.
        self._send_request(
            method="initialize",
            params={
                "processId": process_id,
                "rootUri": root_uri,
                "workspaceFolders": (
                    None
                    if workspace_folders is None
                    else [f.dict() for f in workspace_folders]
                ),
                "trace": trace,
                "capabilities": CAPABILITIES,
            },
        )
        self._state = ClientState.WAITING_FOR_INITIALIZED

    @property
    def state(self) -> ClientState:
        return self._state

    @property
    def is_initialized(self) -> bool:
        return (
            self._state != ClientState.NOT_INITIALIZED
            and self._state != ClientState.WAITING_FOR_INITIALIZED
        )

    def _send_request(self, method: str, params: t.Optional[JSONDict] = None) -> int:
        id = self._id_counter
        self._id_counter += 1

        self._send_buf += _make_request(method=method, params=params, id=id)
        self._unanswered_requests[id] = Request(id=id, method=method, params=params)
        return id

    def _send_notification(
        self, method: str, params: t.Optional[JSONDict] = None
    ) -> None:
        self._send_buf += _make_request(method=method, params=params)

    def _send_response(
        self,
        id: int,
        result: t.Optional[JSONDict] = None,
        error: t.Optional[JSONDict] = None,
    ) -> None:
        self._send_buf += _make_response(id=id, result=result, error=error)

    # response from server
    def _handle_response(self, response: Response) -> Event:
        assert response.id is not None
        request = self._unanswered_requests.pop(response.id)

        if response.error is not None:
            err = ResponseError.parse_obj(response.error)
            err.message_id = response.id
            return err

        event: Event

        if request.method == "initialize":
            assert self._state == ClientState.WAITING_FOR_INITIALIZED
            self._send_notification(
                "initialized", params={}
            )  # params=None doesn't work with gopls
            event = Initialized.parse_obj(response.result)
            self._state = ClientState.NORMAL

        elif request.method == "shutdown":
            assert self._state == ClientState.WAITING_FOR_SHUTDOWN
            event = Shutdown()
            self._state = ClientState.SHUTDOWN

        elif request.method == "textDocument/completion":
            completion_list = None

            try:
                completion_list = CompletionList.parse_obj(response.result)
            except ValidationError:
                try:
                    completion_list = CompletionList(
                        isIncomplete=False,
                        items=parse_obj_as(t.List[CompletionItem], response.result),
                    )
                except ValidationError:
                    assert response.result is None

            event = Completion(message_id=response.id, completion_list=completion_list)

        elif request.method == "textDocument/willSaveWaitUntil":
            event = WillSaveWaitUntilEdits(
                edits=parse_obj_as(t.List[TextEdit], response.result)
            )

        elif request.method == "textDocument/hover":
            if response.result is not None:
                event = Hover.parse_obj(response.result)
            else:
                event = Hover(contents=[])  # null response
            event.message_id = response.id

        elif request.method == "textDocument/signatureHelp":
            if response.result is not None:
                event = SignatureHelp.parse_obj(response.result)
            else:
                event = SignatureHelp(signatures=[])  # null response
            event.message_id = response.id

        elif request.method == "textDocument/documentSymbol":
            event = parse_obj_as(MDocumentSymbols, response)
            event.message_id = response.id

        # GOTOs
        elif request.method == "textDocument/definition":
            event = parse_obj_as(Definition, response)

        elif request.method == "textDocument/references":
            event = parse_obj_as(References, response)
        elif request.method == "textDocument/implementation":
            event = parse_obj_as(Implementation, response)
        elif request.method == "textDocument/declaration":
            event = parse_obj_as(Declaration, response)
        elif request.method == "textDocument/typeDefinition":
            event = parse_obj_as(TypeDefinition, response)

        elif request.method == "textDocument/prepareCallHierarchy":
            event = parse_obj_as(MCallHierarchItems, response)

        elif (
            request.method == "textDocument/formatting"
            or request.method == "textDocument/rangeFormatting"
        ):
            event = parse_obj_as(DocumentFormatting, response)
            event.message_id = response.id

        # WORKSPACE
        elif request.method == "workspace/symbol":
            event = parse_obj_as(MWorkspaceSymbols, response)

        else:
            raise NotImplementedError((response, request))

        return event

    # request from server
    def _handle_request(self, request: Request) -> Event:
        def parse_request(event_cls: t.Type[Event]) -> Event:
            if issubclass(event_cls, ServerRequest):
                event = parse_obj_as(event_cls, request.params)
                assert request.id is not None
                event._id = request.id
                event._client = self
                return event
            elif issubclass(event_cls, ServerNotification):
                return parse_obj_as(event_cls, request.params)
            else:
                raise TypeError(
                    "`event_cls` must be a subclass of ServerRequest"
                    " or ServerNotification"
                )

        if request.method == "workspace/workspaceFolders":
            return parse_request(WorkspaceFolders)

        elif request.method == "workspace/configuration":
            return parse_request(ConfigurationRequest)

        elif request.method == "window/showMessage":
            return parse_request(ShowMessage)
        elif request.method == "window/showMessageRequest":
            return parse_request(ShowMessageRequest)
        elif request.method == "window/logMessage":
            return parse_request(LogMessage)

        elif request.method == "textDocument/publishDiagnostics":
            return parse_request(PublishDiagnostics)

        elif request.method == "window/workDoneProgress/create":
            assert request.params is not None
            event = parse_request(WorkDoneProgressCreate)
            self._progress_tokens_map[request.params["token"]] = WorkDoneProgress
            return event

        elif request.method == "$/progress":
            assert request.params is not None
            progress_type = self._progress_tokens_map.get(request.params["token"])

            if progress_type == WorkDoneProgress:
                assert request.params is not None
                kind = MWorkDoneProgressKind(request.params["value"]["kind"])

                if kind == MWorkDoneProgressKind.BEGIN:
                    return parse_request(WorkDoneProgressBegin)
                elif kind == MWorkDoneProgressKind.REPORT:
                    return parse_request(WorkDoneProgressReport)
                elif kind == MWorkDoneProgressKind.END:
                    del self._progress_tokens_map[request.params["token"]]
                    return parse_request(WorkDoneProgressEnd)

            raise NotImplementedError(request)

        elif request.method == "client/registerCapability":
            return parse_request(RegisterCapabilityRequest)

        else:
            raise NotImplementedError(request)

    def recv(self, data: bytes) -> t.List[Event]:
        self._recv_buf += data

        # _parse_messages deletes consumed data from self._recv_buf
        messages = list(_parse_messages(self._recv_buf))

        events: t.List[Event] = []
        for message in messages:
            try:
                if isinstance(message, Response):
                    events.append(self._handle_response(message))
                elif isinstance(message, Request):
                    events.append(self._handle_request(message))
                else:
                    raise RuntimeError("nobody will ever see this, i hope")
            except Exception:
                logger.exception("Failed to process received message: %s", message)

        return events

    def send(self) -> bytes:
        send_buf = self._send_buf[:]
        self._send_buf.clear()
        return send_buf

    def shutdown(self) -> None:
        assert self._state == ClientState.NORMAL
        self._send_request(method="shutdown")
        self._state = ClientState.WAITING_FOR_SHUTDOWN

    def exit(self) -> None:
        assert self._state == ClientState.SHUTDOWN
        self._send_notification(method="exit", params={})
        self._state = ClientState.EXITED

    def cancel_last_request(self) -> None:
        self._send_notification(
            method="$/cancelRequest", params={"id": self._id_counter - 1}
        )

    def did_open(self, text_document: TextDocumentItem) -> None:
        assert self._state == ClientState.NORMAL
        self._send_notification(
            method="textDocument/didOpen", params={"textDocument": text_document.dict()}
        )

    def did_change(
        self,
        text_document: VersionedTextDocumentIdentifier,
        content_changes: t.List[TextDocumentContentChangeEvent],
    ) -> None:
        assert self._state == ClientState.NORMAL
        self._send_notification(
            method="textDocument/didChange",
            params={
                "textDocument": text_document.dict(),
                "contentChanges": [evt.dict() for evt in content_changes],
            },
        )

    def will_save(
        self, text_document: TextDocumentIdentifier, reason: TextDocumentSaveReason
    ) -> None:
        assert self._state == ClientState.NORMAL
        self._send_notification(
            method="textDocument/willSave",
            params={"textDocument": text_document.dict(), "reason": reason.value},
        )

    def will_save_wait_until(
        self, text_document: TextDocumentIdentifier, reason: TextDocumentSaveReason
    ) -> None:
        assert self._state == ClientState.NORMAL
        self._send_request(
            method="textDocument/willSaveWaitUntil",
            params={"textDocument": text_document.dict(), "reason": reason.value},
        )

    def did_save(
        self, text_document: TextDocumentIdentifier, text: t.Optional[str] = None
    ) -> None:
        assert self._state == ClientState.NORMAL
        params: t.Dict[str, t.Any] = {"textDocument": text_document.dict()}
        if text is not None:
            params["text"] = text
        self._send_notification(method="textDocument/didSave", params=params)

    def did_close(self, text_document: TextDocumentIdentifier) -> None:
        assert self._state == ClientState.NORMAL
        self._send_notification(
            method="textDocument/didClose",
            params={"textDocument": text_document.dict()},
        )

    def did_change_workspace_folders(
        self, added: t.List[WorkspaceFolder], removed: t.List[WorkspaceFolder]
    ) -> None:
        assert self._state == ClientState.NORMAL
        params = {
            "added": [f.dict() for f in added],
            "removed": [f.dict() for f in removed],
        }
        self._send_notification(
            method="workspace/didChangeWorkspaceFolders", params=params
        )

    def completion(
        self,
        text_document_position: TextDocumentPosition,
        context: t.Optional[CompletionContext] = None,
    ) -> int:
        assert self._state == ClientState.NORMAL
        params = {}
        params.update(text_document_position.dict())
        if context is not None:
            params.update(context.dict())
        return self._send_request(method="textDocument/completion", params=params)

    def hover(self, text_document_position: TextDocumentPosition) -> int:
        assert self._state == ClientState.NORMAL
        return self._send_request(
            method="textDocument/hover", params=text_document_position.dict()
        )

    def signatureHelp(self, text_document_position: TextDocumentPosition) -> int:
        assert self._state == ClientState.NORMAL
        return self._send_request(
            method="textDocument/signatureHelp", params=text_document_position.dict()
        )

    def definition(
        self,
        text_document_position: TextDocumentPosition,
        # TODO PartialResultParams
    ) -> int:
        assert self._state == ClientState.NORMAL
        return self._send_request(
            method="textDocument/definition", params=text_document_position.dict()
        )

    def declaration(
        self,
        text_document_position: TextDocumentPosition,
        # TODO PartialResultParams
    ) -> int:
        assert self._state == ClientState.NORMAL
        return self._send_request(
            method="textDocument/declaration", params=text_document_position.dict()
        )

    def typeDefinition(
        self,
        text_document_position: TextDocumentPosition,
        # TODO PartialResultParams
    ) -> int:
        assert self._state == ClientState.NORMAL
        return self._send_request(
            method="textDocument/typeDefinition", params=text_document_position.dict()
        )

    def references(
        self,
        text_document_position: TextDocumentPosition,
        # TODO PartialResultParams
    ) -> int:
        assert self._state == ClientState.NORMAL
        params = {
            "context": {"includeDeclaration": True},
            **text_document_position.dict(),
        }
        return self._send_request(method="textDocument/references", params=params)

    # TODO incomplete
    def prepareCallHierarchy(self, text_document_position: TextDocumentPosition) -> int:
        assert self._state == ClientState.NORMAL
        return self._send_request(
            method="textDocument/prepareCallHierarchy",
            params=text_document_position.dict(),
        )

    def implementation(
        self,
        text_document_position: TextDocumentPosition,
        # TODO PartialResultParams
    ) -> int:
        assert self._state == ClientState.NORMAL
        return self._send_request(
            method="textDocument/implementation", params=text_document_position.dict()
        )

    def workspace_symbol(
        self,
        query: str = "",
        # TODO PartialResultParams
    ) -> int:
        assert self._state == ClientState.NORMAL
        return self._send_request(method="workspace/symbol", params={"query": query})

    def documentSymbol(self, text_document: TextDocumentIdentifier) -> int:
        assert self._state == ClientState.NORMAL
        return self._send_request(
            method="textDocument/documentSymbol",
            params={"textDocument": text_document.dict()},
        )

    def formatting(
        self, text_document: TextDocumentIdentifier, options: FormattingOptions
    ) -> int:
        assert self._state == ClientState.NORMAL
        params = {"textDocument": text_document.dict(), "options": options.dict()}
        return self._send_request(method="textDocument/formatting", params=params)

    def rangeFormatting(
        self,
        text_document: TextDocumentIdentifier,
        range: Range,
        options: FormattingOptions,
    ) -> int:
        assert self._state == ClientState.NORMAL
        params = {
            "textDocument": text_document.dict(),
            "range": range.dict(),
            "options": options.dict(),
        }
        return self._send_request(method="textDocument/rangeFormatting", params=params)
