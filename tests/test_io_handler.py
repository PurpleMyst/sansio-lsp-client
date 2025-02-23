import pytest
from sansio_lsp_client.io_handler import _parse_one_message, _parse_messages
from sansio_lsp_client.structs import MessageType, Request, Response


def test_parse_one_message_request():
    # Create a valid JSON-RPC request message
    content = b'{"jsonrpc": "2.0", "method": "textDocument/didOpen", "id": 1, "params": {}}'
    headers = f'Content-Length: {len(content)}\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n'.encode('ascii')
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
    headers = f'Content-Length: {len(content)}\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n'.encode('ascii')
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
    headers = 'Content-Length: 50\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n'.encode('ascii')
    message = headers + incomplete_content
    
    buffer = bytearray(message)
    
    result = _parse_one_message(buffer)
    assert result is None  # Should return None for incomplete message
    assert len(buffer) == len(message)  # Buffer should remain unchanged


def test_parse_one_message_with_remaining_data():
    # Test parsing when buffer contains more than one message
    first_content = b'{"jsonrpc": "2.0", "method": "textDocument/didOpen", "id": 1, "params": {}}'
    first_headers = f'Content-Length: {len(first_content)}\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n'.encode('ascii')
    first_message = first_headers + first_content
    
    second_message_part = b'Content-Length: 50\r\n'  # Start of next message
    
    buffer = bytearray(first_message + second_message_part)
    
    result = list(_parse_one_message(buffer))
    
    assert len(result) == 1
    assert isinstance(result[0], Request)
    assert result[0].method == "textDocument/didOpen"
    assert len(buffer) == len(second_message_part)  # Only remaining data should be in buffer


def test_parse_one_message_with_array_params():
    # Create a valid JSON-RPC request message
    content = b'{"jsonrpc":"2.0","method":"workspace/projectInitializationComplete","params":[]}'
    headers = f'Content-Length: {len(content)}\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n'.encode('ascii')
    message = headers + content
    
    buffer = bytearray(message)
    
    result = list(_parse_one_message(buffer))
    
    assert len(result) == 1
    assert isinstance(result[0], Request)
    assert result[0].method == "workspace/projectInitializationComplete"
    assert result[0].id is None
    assert result[0].params == []
    assert len(buffer) == 0  # Buffer should be cleared after parsing


def test_parse_messages_response():
    # Create a valid JSON-RPC response message
    message_contents = [
        b'{"jsonrpc":"2.0","method":"window/logMessage","params":{"type":3,"message":"[LanguageServerProjectSystem] Successfully completed load of /Users/me/Project/Project.csproj"}}',
        b'{"jsonrpc":"2.0","method":"window/logMessage","params":{"type":3,"message":"[LanguageServerProjectSystem] Completed (re)load of all projects in 00:00:44.1433469"}}',
        # This next message is malformed, the empty params comes as an empty array instead of an empty dict
        
        b'{"jsonrpc":"2.0","method":"window/logMessage","params":{"type":5,"message":"[LanguageServerHost] [11:28:36.509][End]solution/open"}}',
    ]
    messages = "".join([f'Content-Length: {len(m)}\r\n\r\n'.encode('ascii') + m for m in message_contents])
    
    buffer = bytearray(messages)
    
    result = list(_parse_messages(buffer))
    
    assert len(result) == 4
    assert len(buffer) == 0

    # Let's check the first message 
    assert isinstance(result[0], Request)
    assert result[0].id is None
    assert result[0].method == "window/logMessage"
    assert result[0].params['type'] == MessageType.INFO
    assert result[0].message == ""
