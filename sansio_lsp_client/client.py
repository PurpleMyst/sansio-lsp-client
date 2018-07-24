import enum
from typing import Dict, Any, Iterator

from . import events
from .structs import Request
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

        # Keeps track of which IDs match to which unanswered requests.
        self._unanswered_requests: Dict[int, Request] = {}

        # Just a simple counter to make sure we have unique IDs. We could make
        # sure that this fits into a JSONRPC Number, seeing as Python supports
        # bignums, but I think that's an unlikely enough case that checking for
        # it would just litter the code unnecessarily.
        self._id_counter = 0

    def _make_request(self, method: str, params: Dict[str, Any] = None) -> bytes:
        request = _make_request(method=method, params=params, id=self._id_counter)
        self._unanswered_requests[self._id_counter] = Request(method, params)
        self._id_counter += 1
        return request

    def _make_notification(self, method: str, params: Dict[str, Any] = None) -> bytes:
        return _make_request(method=method, params=params)

    def recieve_bytes(self, data: bytes) -> Iterator[events.Event]:
        self._recv_buf += data

        # We turn the generator into a list so the incomplete request exception
        # is raised before we process anything.
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
                yield events.Initialized(
                    capabilities=response.result["capabilities"],
                    notification=self._make_notification("initialized"),
                )
                self._state = ClientState.NORMAL
            elif request.method == "shutdown":
                assert self._state == ClientState.WAITING_FOR_SHUTDOWN
                yield events.Shatdown()
                self._state = ClientState.SHUTDOWN
            else:
                raise NotImplementedError((response, request))

    def initialize(self, process_id: int = None, root_uri: str = None) -> bytes:
        assert self._state == ClientState.NOT_INITIALIZED
        request = self._make_request(
            method="initialize",
            params={"processId": process_id, "rootUri": root_uri, "capabilities": {}},
        )
        self._state = ClientState.WAITING_FOR_INITIALIZED
        return request

    def shutdown(self) -> bytes:
        assert self._state == ClientState.NORMAL
        request = self._make_request(method="shutdown")
        self._state = ClientState.WAITING_FOR_SHUTDOWN
        return request

    def exit(self) -> bytes:
        assert self._state == ClientState.SHUTDOWN
        request = self._make_notification(method="exit")
        self._state = ClientState.EXITED
        return request
