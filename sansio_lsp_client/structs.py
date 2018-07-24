from typing import NamedTuple, Dict, Any, Optional

Request = NamedTuple("Request", [("method", str), ("params", Optional[Dict[str, Any]])])

Response = NamedTuple(
    "Response",
    [
        ("headers", Dict[str, str]),
        ("id", int),
        ("result", Optional[Dict[str, Any]]),
        ("error", Optional[Dict[str, Any]]),
    ],
)
