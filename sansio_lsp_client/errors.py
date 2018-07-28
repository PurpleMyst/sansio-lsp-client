class IncompleteResponseError(Exception):
    def __init__(self, msg: str, *, missing_bytes: int = None) -> None:
        super().__init__(msg)
        self.missing_bytes = missing_bytes
