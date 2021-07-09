import cgi
import json
import typing as t

from pydantic import parse_obj_as

from .structs import Request, Response, JSONDict


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
    params: t.Optional[JSONDict] = None,
    id: t.Optional[int] = None,
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
    request += _make_headers(content_length=len(encoded_content), encoding=encoding)

    # Append the content to the request
    request += encoded_content

    return request


def _make_response(
    id: int,
    result: t.Optional[JSONDict] = None,
    error: t.Optional[JSONDict] = None,
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
    request += _make_headers(content_length=len(encoded_content), encoding=encoding)

    # Append the content to the request
    request += encoded_content

    return request


# _parse_messages is kind of tricky.
#
# It used to work like this:
#   - Take in bytes argument
#   - Yield parsed things (Responses and Requests)
#   - Raise IncompleteResponseError if parsing fails by running out of bytes
#
# Then, if the bytes contained two valid things (Responses or Requests) and
# then only a part of another thing, this function would first parse and yield
# the valid things and then raise IncompleteResponseError, outputting no
# information about which bytes hadn't been parsed yet. The code calling this
# function would see only the IncompleteResponseError and discard the parsed
# things. Even with that bugginess, this actually worked because every once in
# a while there would be no bytes left from parsing things, and this function
# would output parsed things with no error.
#
# The least error-prone fix I could think of is to pass the bytes to parse
# as a mutable bytearray object, and just delete the used bytes from there.
# This means that we no longer have any need for IncompleteResponseError, and
# this function will return an empty list instead in that case.
#
# _parse_one_message returns None when there are no more messages, and an empty
# iterator when a message was parsed but no things were created.
def _parse_one_message(
    response_buf: bytearray,
) -> t.Optional[t.Iterable[t.Union[Request, Response]]]:
    if b"\r\n\r\n" not in response_buf:
        return None

    header_lines, raw_content = bytes(response_buf).split(b"\r\n\r\n", 1)

    # Many langservers don't set Content-Type header for whatever reason. We
    # use a sane default for that.
    #
    # Langserver spec links to RFC 7230 which says that header names should be
    # case-insensitive.
    headers = {"content-type": "application/vscode-jsonrpc; charset=utf-8"}
    for header_line in header_lines.split(b"\r\n"):
        key, value = header_line.decode("ascii").split(": ", 1)
        headers[key.lower()] = value

    # We will now parse the Content-Type and Content-Length headers. Since for
    # version 3.0 of the Language Server Protocol they're the only ones, we can
    # just verify they're there and not keep them around in the Response
    # object.
    assert set(headers.keys()) == {"content-type", "content-length"}

    # Content-Type and encoding.
    content_type, metadata = cgi.parse_header(headers["content-type"])
    assert content_type == "application/vscode-jsonrpc"
    encoding = metadata["charset"]

    # Content-Length
    content_length = int(headers["content-length"])

    # We need to verify that the raw_content is long enough.
    if len(raw_content) < content_length:
        # incomplete request
        return None

    # Take only as many bytes as we need. If there's any remaining, they're
    # the next response's.
    unused_bytes_count = len(raw_content) - content_length
    raw_content = raw_content[:content_length]

    # This is a good place for deleting unnecessary stuff from response_buf
    # because if the code below fails, then leaving the cause of failure to
    # response_buf would cause this function to fail every time in the future
    # when called with the same response_buf. I think I've had this issue a
    # long time ago, and it was annoying how one response parsing error would
    # also block the parsing of any future responses.
    if unused_bytes_count == 0:  # 'del response_buf[:-0]' does wrong thing
        response_buf.clear()
    else:
        del response_buf[:-unused_bytes_count]

    def parse_request_or_response(data: JSONDict,) -> t.Union[Request, Response]:
        del data["jsonrpc"]
        return parse_obj_as(t.Union[Request, Response], data)  # type: ignore

    content = json.loads(raw_content.decode(encoding))

    if isinstance(content, list):
        # This is in response to a batch operation.
        return map(parse_request_or_response, content)
    else:
        return [parse_request_or_response(content)]


def _parse_messages(response_buf: bytearray,) -> t.Iterator[t.Union[Response, Request]]:
    while True:
        parsed = _parse_one_message(response_buf)
        if parsed is None:
            break
        yield from parsed
