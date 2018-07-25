from .structs import JSONDict, MessageType, MessageActionItem

import typing as t

Initialized = t.NamedTuple("Initialized", [("capabilities", JSONDict)])

Shatdown = t.NamedTuple("Shatdown", [])

ShowMessage = t.NamedTuple(
    "ShowMessage", [("type", MessageType), ("message", str)]
)

ShowMessageRequest = t.NamedTuple(
    "ShowMessageRequest",
    [
        ("type", MessageType),
        ("message", str),
        ("actions", t.Optional[MessageActionItem]),
    ],
)

LogMessage = t.NamedTuple(
    "LogMessage", [("type", MessageType), ("message", str)]
)

Event = t.Union[Initialized, Shatdown, ShowMessage, ShowMessageRequest]
