import enum
import typing as t

from pydantic import parse_obj_as

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
    TextDocumentItem,
    TextDocumentIdentifier,
    VersionedTextDocumentIdentifier,
    TextDocumentContentChangeEvent,
    TextDocumentSaveReason,
    TextEdit,
    Id,
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
        self,
        process_id: t.Optional[int] = None,
        root_uri: t.Optional[str] = None,
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

    @property
    def state(self) -> ClientState:
        return self._state

    def _send_request(
        self, method: str, params: t.Optional[JSONDict] = None
    ) -> int:
        id = self._id_counter
        self._id_counter += 1

        self._send_buf += _make_request(method=method, params=params, id=id)
        self._unanswered_requests[id] = Request(
            id=id, method=method, params=params
        )
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

    def _handle_response(self, response: Response) -> Event:
        assert response.id is not None
        request = self._unanswered_requests.pop(response.id)

        # FIXME: The errors have meanings.
        if response.error is not None:
            __import__("pprint").pprint(response.error)
            raise RuntimeError("Response error!")

        event: Event

        if request.method == "initialize":
            assert self._state == ClientState.WAITING_FOR_INITIALIZED
            self._send_notification("initialized")
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
            except TypeError:
                try:
                    completion_list = CompletionList(
                        isIncomplete=False,
                        items=parse_obj_as(
                            t.List[CompletionItem], response.result
                        ),
                    )
                except TypeError:
                    assert response.result is None

            event = Completion(
                message_id=response.id, completion_list=completion_list
            )

        elif request.method == "textDocument/willSaveWaitUntil":
            event = WillSaveWaitUntilEdits(
                edits=parse_obj_as(t.List[TextEdit], response.result)
            )

        else:
            raise NotImplementedError((response, request))

        return event

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

        if request.method == "window/showMessage":
            return parse_request(ShowMessage)
        elif request.method == "window/showMessageRequest":
            return parse_request(ShowMessageRequest)
        elif request.method == "window/logMessage":
            return parse_request(LogMessage)
        elif request.method == "textDocument/publishDiagnostics":
            return parse_request(PublishDiagnostics)
        else:
            raise NotImplementedError(request)

    def recv(self, data: bytes) -> t.List[Event]:
        self._recv_buf += data

        # _parse_messages deletes consumed data from self._recv_buf
        messages = list(_parse_messages(self._recv_buf))

        events: t.List[Event] = []
        for message in messages:
            if isinstance(message, Response):
                events.append(self._handle_response(message))
            elif isinstance(message, Request):
                events.append(self._handle_request(message))
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
            params={"textDocument": text_document.dict()},
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
        self,
        text_document: TextDocumentIdentifier,
        reason: TextDocumentSaveReason,
    ) -> None:
        assert self._state == ClientState.NORMAL
        self._send_notification(
            method="textDocument/willSave",
            params={
                "textDocument": text_document.dict(),
                "reason": reason.value,
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
                "textDocument": text_document.dict(),
                "reason": reason.value,
            },
        )

    def did_save(
        self,
        text_document: TextDocumentIdentifier,
        text: t.Optional[str] = None,
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

    def completions(
        self,
        text_document_position: TextDocumentPosition,
        context: t.Optional[CompletionContext] = None,
    ) -> int:
        assert self._state == ClientState.NORMAL
        params = {}
        params.update(text_document_position.dict())
        if context is not None:
            params.update(context.dict())
        return self._send_request(
            method="textDocument/completion", params=params
        )
