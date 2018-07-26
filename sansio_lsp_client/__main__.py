#!/usr/bin/env python3
# just a canvas to play in.
import os
import pprint
import socket
import urllib.request

from .client import Client
from .errors import IncompleteResponseError
from .events import Initialized, Shutdown, ShowMessageRequest, Completion
from .structs import (
    CompletionTriggerKind,
    TextDocumentItem,
    TextDocumentPosition,
    CompletionContext,
    TextDocumentIdentifier,
    VersionedTextDocumentIdentifier,
    TextDocumentContentChangeEvent,
    TextDocumentSaveReason,
    Position,
)


def main() -> None:
    sock = socket.socket()
    sock.connect(("localhost", int(os.environ.get("PORT", 8080))))

    client = Client(trace="verbose")

    file_path = "./playground.py"
    file_uri = "file://" + urllib.request.pathname2url(
        os.path.abspath(file_path)
    )
    print("File URI:", file_uri)

    while True:
        sock.sendall(client.send())

        try:
            data = sock.recv(4096)
            if not data:
                break
            events = list(client.recv(data))
        except IncompleteResponseError as e:
            continue

        for event in events:
            if isinstance(event, Initialized):
                print("Initialized!")

                print("Server capabilities:")
                pprint.pprint(event.capabilities)

                client.did_open(
                    TextDocumentItem(
                        uri=file_uri,
                        languageId="python",
                        text=open(file_path).read(),
                        version=0,
                    )
                )

                client.completions(
                    text_document_position=TextDocumentPosition(
                        textDocument=TextDocumentIdentifier(uri=file_uri),
                        position=Position(
                            line=5, character=4 + len("struct.") + 1
                        ),
                    ),
                    context=CompletionContext(
                        triggerKind=CompletionTriggerKind.INVOKED
                    ),
                )
            elif isinstance(event, Shutdown):
                print("Shutdown and exiting")
                client.exit()
            elif isinstance(event, Completion):
                print("Completions:")
                pprint.pprint(
                    [item.label for item in event.completion_list.items]
                )

                client.did_close(
                    text_document=TextDocumentIdentifier(uri=file_uri)
                )

                client.will_save(
                    text_document=TextDocumentIdentifier(uri=file_uri),
                    reason=TextDocumentSaveReason.MANUAL,
                )

                client.did_save(
                    text_document=TextDocumentIdentifier(uri=file_uri)
                )

                client.shutdown()
                client.cancel_last_request()
            else:
                raise NotImplementedError(event)


if __name__ == "__main__":
    main()
