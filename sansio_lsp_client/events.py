import typing as t

import attr
from attr import attrs, attrib

from .structs import (
    JSONDict,
    Range,
    MessageType,
    MessageActionItem,
    CompletionItem,
    CompletionList,
    TextEdit,
)


@attrs
class Event:
    pass


@attrs
class ServerRequest(Event):
    _client: "Client" = attrib(init=False)
    _id: int = attrib(init=False)


@attrs
class ServerNotification(Event):
    pass


@attrs
class Initialized(Event):
    capabilities: JSONDict = attrib()


@attrs
class Shutdown(Event):
    pass


@attrs
class ShowMessage(ServerNotification):
    type: MessageType = attrib()
    message: str = attrib()


@attrs
class ShowMessageRequest(ServerRequest):
    type: MessageType = attrib()
    message: str = attrib()
    actions: t.Optional[t.List[MessageActionItem]] = attrib()

    def reply(self, action: MessageActionItem = None) -> None:
        """
        Reply to the ShowMessageRequest with the user's selection.

        No bytes are actually returned from this method, the reply's bytes are added to the client's internal send buffer.
        """
        self._client._send_response(id=self._id, result=attr.asdict(action))


@attrs
class LogMessage(ServerNotification):
    type: MessageType = attrib()
    message: str = attrib()


@attrs
class Completion:
    completion_list: t.Union[
        CompletionList, t.List[CompletionItem], None
    ] = attrib()


# XXX: not sure how to name this event.
@attrs
class WillSaveWaitUntilEdits:
    edits: t.Optional[t.List[TextEdit]] = attrib(default=None)


@attrs
class Location:
    uri: str = attrib()
    range: Range = attrib()


@attrs
class DiagnosticRelatedInformation:
    location: Location = attrib()
    message: str = attrib()


@attrs
class Diagnostic:
    range: Range = attrib()

    # TODO: Make this a proper enum
    severity: int = attrib(default=None)

    # TODO: Support this as an union of str and int
    code: t.Optional[t.Any] = attrib(default=None)

    source: t.Optional[str] = attrib(default=None)

    message: t.Optional[str] = attrib(default=None)

    relatedInformation: t.Optional[
        t.List[DiagnosticRelatedInformation]
    ] = attrib(default=None)


@attrs
class PublishDiagnostics(ServerNotification):
    uri: str = attrib()
    diagnostics: t.List[Diagnostic] = attrib()
