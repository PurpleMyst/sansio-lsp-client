#!/usr/bin/env python3
# just a canvas to play in.
import json
import os
import pprint
import socket

from .client import Client
from .errors import IncompleteResponseError
from .events import Initialized, Shutdown, ShowMessageRequest


def main() -> None:
    sock = socket.socket()
    sock.connect(("localhost", int(os.environ.get("PORT", 8080))))

    client = Client(trace="verbose")

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
                print("Capabilities:")
                pprint.pprint(event.capabilities)

                request = json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 42,
                        "method": "window/showMessageRequest",
                        "params": {
                            "type": 3,
                            "message": "Save or destroy?",
                            "actions": [
                                {"title": "Save"},
                                {"title": "Destroy"},
                            ],
                        },
                    }
                ).encode("utf-8")
                events = list(
                    client.recv(
                        b"Content-Length: %d\r\n" % len(request)
                        + b"Content-Type: application/vscode-jsonrpc; charset=utf8\r\n"
                        + b"\r\n"
                        + request
                    )
                )
                pprint.pprint(events[0])

                client.shutdown()
            elif isinstance(event, Shutdown):
                print("Shutdown and exiting")
                client.exit()
            else:
                raise NotImplementedError(event)


if __name__ == "__main__":
    main()
