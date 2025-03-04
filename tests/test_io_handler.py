from sansio_lsp_client.io_handler import _parse_one_message
from sansio_lsp_client.structs import Request, Response


def test_parse_one_message_request():
    # Create a valid JSON-RPC request message
    content = (
        b'{"jsonrpc": "2.0", "method": "textDocument/didOpen", "id": 1, "params": {}}'
    )
    headers = f"Content-Length: {len(content)}\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n".encode(
        "ascii"
    )
    message = headers + content

    buffer = bytearray(message)

    result = list(_parse_one_message(buffer))

    assert len(result) == 1
    assert isinstance(result[0], Request)
    assert result[0].method == "textDocument/didOpen"
    assert result[0].id == 1
    assert result[0].params == {}
    assert len(buffer) == 0  # Buffer should be cleared after parsing


def test_parse_one_message_response():
    # Create a valid JSON-RPC response message
    content = b'{"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}'
    headers = f"Content-Length: {len(content)}\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n".encode(
        "ascii"
    )
    message = headers + content

    buffer = bytearray(message)

    result = list(_parse_one_message(buffer))

    assert len(result) == 1
    assert isinstance(result[0], Response)
    assert result[0].id == 1
    assert result[0].result == {"capabilities": {}}
    assert result[0].error is None
    assert len(buffer) == 0


def test_parse_one_message_incomplete():
    # Test with incomplete message
    incomplete_content = b'{"jsonrpc": "2.0", "id": 1, "res'  # Incomplete content
    headers = "Content-Length: 50\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n".encode(
        "ascii"
    )
    message = headers + incomplete_content

    buffer = bytearray(message)

    result = _parse_one_message(buffer)
    assert result is None  # Should return None for incomplete message
    assert len(buffer) == len(message)  # Buffer should remain unchanged


def test_parse_one_message_with_remaining_data():
    # Test parsing when buffer contains more than one message
    first_content = (
        b'{"jsonrpc": "2.0", "method": "textDocument/didOpen", "id": 1, "params": {}}'
    )
    first_headers = f"Content-Length: {len(first_content)}\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n".encode(
        "ascii"
    )
    first_message = first_headers + first_content

    second_message_part = b"Content-Length: 50\r\n"  # Start of next message

    buffer = bytearray(first_message + second_message_part)

    result = list(_parse_one_message(buffer))

    assert len(result) == 1
    assert isinstance(result[0], Request)
    assert result[0].method == "textDocument/didOpen"
    assert len(buffer) == len(
        second_message_part
    )  # Only remaining data should be in buffer


def test_parse_one_message_with_array_params():
    # Create a valid JSON-RPC request message
    content = b'{"jsonrpc":"2.0","method":"workspace/projectInitializationComplete","params":[]}'
    headers = f"Content-Length: {len(content)}\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n".encode(
        "ascii"
    )
    message = headers + content

    buffer = bytearray(message)

    result = list(_parse_one_message(buffer))

    assert len(result) == 1
    assert isinstance(result[0], Request)
    assert result[0].method == "workspace/projectInitializationComplete"
    assert result[0].id is None
    assert result[0].params == []
    assert len(buffer) == 0  # Buffer should be cleared after parsing