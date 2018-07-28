import enum
import typing as t

import cattr

from .events import (
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
)
from .structs import (
    Response,
    TextDocumentPosition,
    CompletionContext,
    CompletionList,
    CompletionItem,
    Request,
    JSONDict,
    MessageActionItem,
    MessageType,
    TextDocumentItem,
    TextDocumentIdentifier,
    VersionedTextDocumentIdentifier,
    TextDocumentContentChangeEvent,
    TextDocumentSaveReason,
)
from .io_handler import _make_request, _parse_messages, _make_response


class ClientState(enum.Enum):
    NOT_INITIALIZED = enum.auto()
    WAITING_FOR_INITIALIZED = enum.auto()
    NORMAL = enum.auto()
    WAITING_FOR_SHUTDOWN = enum.auto()
    SHUTDOWN = enum.auto()
    EXITED = enum.auto()


class Client:
    # TODO: Save the encoding given here.
    def __init__(
        self, process_id: int = None, root_uri: str = None, trace: str = "off"
    ) -> None:
        self._state = ClientState.NOT_INITIALIZED

        # Used to save data as it comes in (from `recieve_bytes`) until we have
        # a full request.
        self._recv_buf = bytearray()

        # Things that we still need to send.
        self._send_buf = bytearray()

        # Keeps track of which IDs match to which unanswered requests.
        self._unanswered_requests: t.Dict[int, Request] = {}

        # Just a simple counter to make sure we have unique IDs. We could make
        # sure that this fits into a JSONRPC Number, seeing as Python supports
        # bignums, but I think that's an unlikely enough case that checking for
        # it would just litter the code unnecessarily.
        self._id_counter = 0

        # We'll just immediately send off an "initialize" request.
        self._send_request(
            method="initialize",
            params={
                "processId": process_id,
                "rootUri": root_uri,
                "capabilities": {},
                "trace": trace,
            },
        )
        self._state = ClientState.WAITING_FOR_INITIALIZED

    def _send_request(self, method: str, params: JSONDict = None) -> None:
        request = _make_request(
            method=method, params=params, id=self._id_counter
        )
        self._send_buf += request
        self._unanswered_requests[self._id_counter] = Request(
            id=self._id_counter, method=method, params=params
        )
        self._id_counter += 1

    def _send_notification(self, method: str, params: JSONDict = None) -> None:
        self._send_buf += _make_request(method=method, params=params)

    def _send_response(
        self, id: int, result: JSONDict = None, error: JSONDict = None
    ) -> None:
        self._send_buf += _make_response(id=id, result=result, error=error)

    def recv(self, data: bytes) -> t.List[Event]:
        self._recv_buf += data

        # We must exhaust the generator so IncompleteResponseError
        # is raised before we actually process anything.
        messages = list(_parse_messages(self._recv_buf))

        # If we get here, that means the previous line didn't error out so we
        # can just clear whatever we were holding.
        self._recv_buf.clear()

        events = []
        for message in messages:
            if isinstance(message, Response):
                response = message
                request = self._unanswered_requests.pop(response.id)

                # FIXME: The errors have meanings.
                if response.error is not None:
                    __import__("pprint").pprint(response.error)
                    raise RuntimeError("Response error!")

                if request.method == "initialize":
                    assert self._state == ClientState.WAITING_FOR_INITIALIZED
                    self._send_notification("initialized")
                    events.append(
                        cattr.structure(response.result, Initialized)
                    )
                    self._state = ClientState.NORMAL
                elif request.method == "shutdown":
                    assert self._state == ClientState.WAITING_FOR_SHUTDOWN
                    events.append(Shutdown())
                    self._state = ClientState.SHUTDOWN
                elif request.method == "textDocument/completion":
                    completion_list = None

                    try:
                        completion_list = cattr.structure(
                            response.result, CompletionList
                        )
                    except TypeError:
                        try:
                            completion_list = CompletionList(
                                isIncomplete=False,
                                items=cattr.structure(
                                    response.result, t.List[CompletionItem]
                                ),
                            )
                        except TypeError:
                            assert response.result is None

                    events.append(Completion(completion_list))
                elif request.method == "textDocument/willSaveWaitUntil":
                    events.append(
                        WillSaveWaitUntilEdits(edits=response.result)
                    )
                else:
                    raise NotImplementedError((response, request))
            elif isinstance(message, Request):
                request = message

                E = t.TypeVar("E", bound=Event)

                def structure_request(event_cls: t.Type[E]) -> E:
                    if issubclass(event_cls, ServerRequest):
                        event = cattr.structure(request.params, event_cls)
                        event._id = request.id
                        event._client = self
                        return event
                    elif issubclass(event_cls, ServerNotification):
                        return cattr.structure(request.params, event_cls)
                    else:
                        raise TypeError(
                            "`event_cls` must be a subclass of ServerRequest or ServerNotification"
                        )

                if request.method == "window/showMessage":
                    events.append(structure_request(ShowMessage))
                elif request.method == "window/showMessageRequest":
                    events.append(structure_request(ShowMessageRequest))
                elif request.method == "window/logMessage":
                    events.append(structure_request(LogMessage))
                elif request.method == "textDocument/publishDiagnostics":
                    events.append(structure_request(PublishDiagnostics))
                else:
                    raise NotImplementedError(request)
            else:
                raise RuntimeError("nobody will ever see this, i hope")

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
        self._send_notification(method="exit")
        self._state = ClientState.EXITED

    def cancel_last_request(self) -> None:
        self._send_notification(
            method="$/cancelRequest", params={"id": self._id_counter - 1}
        )

    def did_open(self, text_document: TextDocumentItem) -> None:
        assert self._state == ClientState.NORMAL
        self._send_notification(
            method="textDocument/didOpen",
            params={"textDocument": cattr.unstructure(text_document)},
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
                "textDocument": cattr.unstructure(text_document),
                "contentChanges": cattr.unstructure(content_changes),
            },
        )

    def will_save(
        self,
        text_document: TextDocumentIdentifier,
        reason: TextDocumentSaveReason,
    ) -> None:
        assert self._state == ClientState.NORMAL
        self._send_notification(
            method="textDocument/willSave",
            params={
                "textDocument": cattr.unstructure(text_document),
                "reason": cattr.unstructure(reason),
            },
        )

    def will_save_wait_until(
        self,
        text_document: TextDocumentIdentifier,
        reason: TextDocumentSaveReason,
    ) -> None:
        assert self._state == ClientState.NORMAL
        self._send_request(
            method="textDocument/willSaveWaitUntil",
            params={
                "textDocument": cattr.unstructure(text_document),
                "reason": cattr.unstructure(reason),
            },
        )

    def did_save(
        self, text_document: TextDocumentIdentifier, text: str = None
    ) -> None:
        assert self._state == ClientState.NORMAL
        params = {"textDocument": cattr.unstructure(text_document)}
        if text is not None:
            params["text"] = text
        self._send_notification(method="textDocument/didSave", params=params)

    def did_close(self, text_document: TextDocumentIdentifier) -> None:
        assert self._state == ClientState.NORMAL
        self._send_notification(
            method="textDocument/didClose",
            params={"textDocument": cattr.unstructure(text_document)},
        )

    def completions(
        self,
        text_document_position: TextDocumentPosition,
        context: CompletionContext = None,
    ) -> None:
        assert self._state == ClientState.NORMAL
        params = {}
        params.update(cattr.unstructure(text_document_position))
        if context is not None:
            params.update(cattr.unstructure(context))
        self._send_request(method="textDocument/completion", params=params)
