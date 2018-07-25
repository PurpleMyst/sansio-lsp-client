#!/usr/bin/env python3
# just a canvas to play in.
import socket
import os

from .client import Client
from .errors import IncompleteResponseError
from .events import Initialized, Shatdown


def main() -> None:
    sock = socket.socket()
    sock.connect(("localhost", int(os.environ.get("PORT", 8080))))

    client = Client()
    client.initialize()

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
                __import__("pprint").pprint(event.capabilities)

                print("Shutting down")
                client.shutdown()
            elif isinstance(event, Shatdown):
                print("Shutdown and exiting")
                client.exit()
            else:
                raise NotImplementedError(event)


if __name__ == "__main__":
    main()
