import enum
import typing as t

from . import events
from .structs import Request, JSONDict
from .io_handler import _make_request, _parse_responses


class ClientState(enum.Enum):
    NOT_INITIALIZED = enum.auto()
    WAITING_FOR_INITIALIZED = enum.auto()
    NORMAL = enum.auto()
    WAITING_FOR_SHUTDOWN = enum.auto()
    SHUTDOWN = enum.auto()
    EXITED = enum.auto()


class Client:
    def __init__(self) -> None:
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

    def _send_request(self, method: str, params: JSONDict = None) -> None:
        request = _make_request(
            method=method, params=params, id=self._id_counter
        )
        self._send_buf += request
        self._unanswered_requests[self._id_counter] = Request(method, params)
        self._id_counter += 1

    def _send_notification(self, method: str, params: JSONDict = None) -> None:
        self._send_buf += _make_request(method=method, params=params)

    def recv(self, data: bytes) -> t.Iterator[events.Event]:
        self._recv_buf += data

        # We must exhaust the generator so IncompleteResponseError
        # is raised before we actually process anything.
        responses = list(_parse_responses(self._recv_buf))

        # If we get here, that means the previous line didn't error out so we
        # can just clear whatever we were holding.
        self._recv_buf.clear()

        for response in responses:
            request = self._unanswered_requests.pop(response.id)

            # FIXME: Do something more with the errors.
            if response.error is not None:
                raise Exception(response.error)

            if request.method == "initialize":
                assert self._state == ClientState.WAITING_FOR_INITIALIZED
                assert response.result is not None
                self._send_notification("initialized")
                yield events.Initialized(
                    capabilities=response.result["capabilities"]
                )
                self._state = ClientState.NORMAL
            elif request.method == "shutdown":
                assert self._state == ClientState.WAITING_FOR_SHUTDOWN
                yield events.Shatdown()
                self._state = ClientState.SHUTDOWN
            else:
                raise NotImplementedError((response, request))

    def send(self) -> bytes:
        send_buf = self._send_buf[:]
        self._send_buf.clear()
        return send_buf

    # XXX: Should we just move this into `__init__`?
    def initialize(self, process_id: int = None, root_uri: str = None) -> None:
        assert self._state == ClientState.NOT_INITIALIZED
        self._send_request(
            method="initialize",
            params={
                "processId": process_id,
                "rootUri": root_uri,
                "capabilities": {},
            },
        )
        self._state = ClientState.WAITING_FOR_INITIALIZED

    def shutdown(self) -> None:
        assert self._state == ClientState.NORMAL
        self._send_request(method="shutdown")
        self._state = ClientState.WAITING_FOR_SHUTDOWN

    def exit(self) -> None:
        assert self._state == ClientState.SHUTDOWN
        self._send_notification(method="exit")
        self._state = ClientState.EXITED
