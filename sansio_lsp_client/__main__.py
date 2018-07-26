#!/usr/bin/env python3
# just a canvas to play in.
import json
import os
import pprint
import socket
import urllib.request

from .client import Client
from .errors import IncompleteResponseError
from .events import Initialized, Shutdown, ShowMessageRequest
from .structs import (
    TextDocumentItem,
    TextDocumentIdentifier,
    VersionedTextDocumentIdentifier,
    TextDocumentContentChangeEvent,
)


def main() -> None:
    sock = socket.socket()
    sock.connect(("localhost", int(os.environ.get("PORT", 8080))))

    client = Client(trace="verbose")

    file_path = "sansio_lsp_client/client.py"
    file_uri = "file://" + urllib.request.pathname2url(
        os.path.abspath(file_path)
    )

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

                client.did_change(
                    text_document=TextDocumentIdentifier(uri=file_uri),
                    content_changes=[
                        TextDocumentContentChangeEvent.from_python(0, 2, "!#")
                    ],
                )

                # TODO: Ask for completions here.

                client.did_close(
                    text_document=TextDocumentIdentifier(uri=file_uri)
                )

                client.shutdown()
            elif isinstance(event, Shutdown):
                print("Shutdown and exiting")
                client.exit()
            else:
                raise NotImplementedError(event)


if __name__ == "__main__":
    main()
