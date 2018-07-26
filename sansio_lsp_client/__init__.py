"""An implementation of the client side of the LSP protocol, useful for embedding easily in your editor."""

from .client import Client
from .events import *
from .structs import *

__version__ = "0.2.2"
