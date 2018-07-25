import typing as t

# This is useful for some nice typing. The `Any`s are meant to be `JSONValue`,
# but nested types aren't supported. Sadly this leads to a false positive for
# an error in client.py:69.
JSONValue = t.Union[None, str, int, t.List[t.Any], t.Dict[str, t.Any]]
JSONDict = t.Dict[str, JSONValue]

Request = t.NamedTuple(
    "Request", [("method", str), ("params", t.Optional[JSONDict])]
)

Response = t.NamedTuple(
    "Response",
    [
        ("headers", t.Dict[str, str]),
        ("id", int),
        ("result", t.Optional[JSONDict]),
        ("error", t.Optional[JSONDict]),
    ],
)
