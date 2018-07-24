import cgi
import json

from .structs import Response
from .errors import IncompleteResponseError


def _make_request(method, params=None, id=None, encoding="utf-8"):
    request = bytearray()

    # Set up the actual JSONRPC content and encode it.
    content = {
        "jsonrpc": "2.0",
        "method": method,
    }
    if params is not None:
        content["params"] = params
    if id is not None:
        content["id"] = id
    content = json.dumps(content).encode(encoding)

    # Write the headers to the request body
    headers = {
        "Content-Length": len(content),
        "Content-Type": f"application/vscode-jsonrpc; charset={encoding}",
    }
    for (key, value) in headers.items():
        request += f"{key}: {value}\r\n".encode(encoding)
    request += b"\r\n"

    # Append the content to the request
    request += content

    return request


def _parse_responses(response):
    if b"\r\n\r\n" not in response:
        raise IncompleteResponseError("Incomplete headers")

    header_lines, content = response.split(b"\r\n\r\n", 1)

    # Parse the headers.
    headers = {}
    for header_line in header_lines.split(b"\r\n"):
        key, value = header_line.decode("ascii").split(": ", 1)
        headers[key] = value

    # Let's now verify and parse a few headers. Well, the only headers
    # supported currently.
    assert "Content-Length" in headers
    assert "Content-Type" in headers

    # Content-Type and encoding.
    content_type, metadata = cgi.parse_header(headers["Content-Type"])
    assert content_type == "application/vscode-jsonrpc"
    encoding = metadata["charset"]

    # Content-Length
    content_length = int(headers["Content-Length"])

    # We need to verify that the content is long enough, seeing as we might be
    # getting an incomplete request.
    if len(content) < content_length:
        raise IncompleteResponseError("Not enough bytes to "
                                      "fulfill Content-Length requirements.")

    # Take only as many bytes as we need. If there's any remaining, they're
    # the next response's.
    content, next_response = \
        content[:content_length], content[content_length:]

    content = json.loads(content.decode(encoding))
    yield Response(headers,
                   id=int(content["id"]),
                   result=content.get("result"),
                   error=content.get("error"))

    if next_response:
        yield from _parse_responses(next_response)
