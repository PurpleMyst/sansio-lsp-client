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

    sock.sendall(client.initialize())

    while True:
        try:
            data = sock.recv(4096)
            if not data:
                break
            events = list(client.recieve_bytes(data))
        except IncompleteResponseError as e:
            continue

        for event in events:
            if isinstance(event, Initialized):
                print("Initialized!")
                print("Capabilities:")
                __import__("pprint").pprint(event.capabilities)
                sock.sendall(event.notification)

                print("Shutting down")
                sock.sendall(client.shutdown())
            elif isinstance(event, Shatdown):
                print("Shutdown and exiting")
                sock.sendall(client.exit())
            else:
                raise NotImplementedError(event)


if __name__ == "__main__":
    main()
