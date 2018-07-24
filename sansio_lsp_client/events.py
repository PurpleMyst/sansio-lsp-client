from typing import NamedTuple, Dict, Any, Union

Initialized = NamedTuple(
    "Initialized", [("capabilities", Dict[str, Any]), ("notification", bytes)]
)

Shatdown = NamedTuple("Shatdown", [])

Event = Union[Initialized, Shatdown]
