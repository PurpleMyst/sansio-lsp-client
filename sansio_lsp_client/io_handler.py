import cgi
import json
import typing as t

import cattr

from .structs import Request, Response, JSONDict
from .errors import IncompleteResponseError


def _make_headers(content_length: int, encoding: str = "utf-8") -> bytes:
    headers_bytes = bytearray()
    headers = {
        "Content-Length": content_length,
        "Content-Type": f"application/vscode-jsonrpc; charset={encoding}",
    }
    for (key, value) in headers.items():
        headers_bytes += f"{key}: {value}\r\n".encode(encoding)
    headers_bytes += b"\r\n"
    return headers_bytes


def _make_request(
    method: str,
    params: JSONDict = None,
    id: int = None,
    *,
    encoding: str = "utf-8",
) -> bytes:
    request = bytearray()

    # Set up the actual JSONRPC content and encode it.
    content: JSONDict = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        content["params"] = params
    if id is not None:
        content["id"] = id
    encoded_content = json.dumps(content).encode(encoding)

    # Write the headers to the request body
    request += _make_headers(
        content_length=len(encoded_content), encoding=encoding
    )

    # Append the content to the request
    request += encoded_content

    return request


def _make_response(
    id: int,
    result: JSONDict = None,
    error: JSONDict = None,
    *,
    encoding: str = "utf-8",
) -> bytes:
    request = bytearray()

    # Set up the actual JSONRPC content and encode it.
    content: JSONDict = {"jsonrpc": "2.0", "id": id}
    if result is not None:
        content["result"] = result
    if error is not None:
        content["error"] = error
    encoded_content = json.dumps(content).encode(encoding)

    # Write the headers to the request body
    request += _make_headers(
        content_length=len(encoded_content), encoding=encoding
    )

    # Append the content to the request
    request += encoded_content

    return request


def _parse_messages(response: bytes) -> t.Iterator[t.Union[Response, Request]]:
    if b"\r\n\r\n" not in response:
        raise IncompleteResponseError("Incomplete headers")

    header_lines, raw_content = response.split(b"\r\n\r\n", 1)

    # Parse the headers.
    headers = {}
    for header_line in header_lines.split(b"\r\n"):
        key, value = header_line.decode("ascii").split(": ", 1)
        headers[key] = value

    # We will now parse the Content-Type and Content-Length headers. Since for
    # version 3.0 of the Language Server Protocol they're the only ones, we can
    # just verify they're there and not keep them around in the Response
    # object.
    assert set(headers.keys()) == {"Content-Type", "Content-Length"}

    # Content-Type and encoding.
    content_type, metadata = cgi.parse_header(headers["Content-Type"])
    assert content_type == "application/vscode-jsonrpc"
    encoding = metadata["charset"]

    # Content-Length
    content_length = int(headers["Content-Length"])

    # We need to verify that the raw_content is long enough, seeing as we might
    # be getting an incomplete request.
    if len(raw_content) < content_length:
        raise IncompleteResponseError(
            "Not enough bytes to fulfill Content-Length requirements.",
            missing_bytes=content_length - len(raw_content),
        )

    # Take only as many bytes as we need. If there's any remaining, they're
    # the next response's.
    raw_content, next_response = (
        raw_content[:content_length],
        raw_content[content_length:],
    )

    def do_it(data: JSONDict) -> t.Union[Response, Request]:
        del data["jsonrpc"]

        try:
            response = cattr.structure(data, Response)
            return response
        except TypeError:
            pass

        try:
            request = cattr.structure(data, Request)
            return request
        except TypeError:
            pass

        raise RuntimeError(f"{data!r} is neither a Request nor a Response!")

    content = json.loads(raw_content.decode(encoding))
    if isinstance(content, list):
        # This is in response to a batch operation.
        yield from map(do_it, content)
    else:
        yield do_it(content)

    if next_response:
        yield from _parse_messages(next_response)
