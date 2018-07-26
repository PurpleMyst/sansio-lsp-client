import typing as t

import attr
from attr import attrs, attrib

from .structs import JSONDict, MessageType, MessageActionItem


@attrs
class Event:
    pass


@attrs
class Initialized(Event):
    capabilities: JSONDict = attrib()


@attrs
class Shutdown(Event):
    pass


@attrs
class ShowMessage(Event):
    type: MessageType = attrib()
    message: str = attrib()


@attrs
class ShowMessageRequest(Event):
    type: MessageType = attrib()
    message: str = attrib()
    actions: t.Optional[t.List[MessageActionItem]] = attrib()

    _client: "Client" = attrib(init=False)
    _id: int = attrib(init=False)

    def reply(self, action: MessageActionItem = None) -> None:
        """
        Reply to the ShowMessageRequest with the user's selection.

        No bytes are actually returned from this method, the reply's bytes are added to the client's internal send buffer.
        """
        self._client._send_response(id=self._id, result=attr.asdict(action))


@attrs
class LogMessage(Event):
    type: MessageType = attrib()
    message: str = attrib()
