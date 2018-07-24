import enum

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
    def __init__(self):
        self._state = ClientState.NOT_INITIALIZED

        # Used to save data as it comes in (from `recieve_bytes`) until we have
        # a full request.
        self._recv_buf = bytearray()

        # Keeps track of which IDs match to which unanswered requests.
        self._unanswered_requests = {}

        # Just a simple counter to make sure we have unique IDs. We could make
        # sure that this fits into a JSONRPC Number, seeing as Python supports
        # bignums, but I think that's an unlikely enough case that checking for
        # it would just litter the code unnecessarily.
        self._id_counter = 0

    def _make_request(self, method, params=None):
        request = _make_request(
            method=method,
            params=params,
            id=self._id_counter,
        )
        self._unanswered_requests[self._id_counter] = \
            Request(method, params)
        self._id_counter += 1
        return request

    def _make_notification(self, method, params=None):
        return _make_request(
            method=method,
            params=params,
        )

    def recieve_bytes(self, data):
        self._recv_buf += data
        responses = _parse_responses(self._recv_buf)

        for response in responses:
            request = self._unanswered_requests.pop(response.id)

            if request.method == "initialize":
                assert self._state == ClientState.WAITING_FOR_INITIALIZED
                yield events.Initialized(self._make_notification("initialized"))
                self._state = ClientState.NORMAL
            elif request.method == "shutdown":
                assert self._state == ClientState.WAITING_FOR_SHUTDOWN
                yield events.Shatdown()
                self._state = ClientState.SHUTDOWN
            else:
                raise NotImplementedError((response, request))

        self._recv_buf.clear()

    def initialize(self, process_id=None, root_uri=None):
        assert self._state == ClientState.NOT_INITIALIZED
        request = self._make_request(
            method="initialize",
            params={
                "processId": process_id,
                "rootUri": root_uri,
                "capabilities": {}
            },
        )
        self._state = ClientState.WAITING_FOR_INITIALIZED
        return request

    def shutdown(self):
        # XXX: Can we shutdown from other states?
        assert self._state == ClientState.NORMAL
        request = self._make_request(
            method="shutdown",
        )
        self._state = ClientState.WAITING_FOR_SHUTDOWN
        return request

    def exit(self):
        assert self._state == ClientState.SHUTDOWN
        request = self._make_notification(
            method="exit",
        )
        self._state = ClientState.EXITED
        return request
