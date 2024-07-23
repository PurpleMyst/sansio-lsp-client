set windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]

test-pyright:
    poetry run pytest -s -v -k pyright
