from .structs import JSONDict

import typing as t

Initialized = t.NamedTuple("Initialized", [("capabilities", JSONDict)])

Shatdown = t.NamedTuple("Shatdown", [])

Event = t.Union[Initialized, Shatdown]
