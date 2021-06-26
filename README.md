# sansio-lsp-client

An implementation of the client side of the LSP protocol, useful for embedding
easily in your editor.


## Developing

    $ git clone https://github.com/PurpleMyst/sansio-lsp-client
    $ cd sansio-lsp-client
    $ python3 -m venv env
    $ source env/bin/activate
    (env)$ pip install --upgrade pip
    (env)$ pip install poetry
    (env)$ poetry install

To run tests, you currently need a non-Windows system.
First download the langservers you need.
You can mostly read `.github/workflows/test.yml`, but there are some gotchas:

- If you want to install the Go langserver, you will need to install go from https://golang.org/.
    The one from `sudo apt install golang` is too old.
    Extract it to `go/` inside `sansio-lsp-client`:

        $ tar xf /blah/blah/Downloads/go1.16.5.linux-amd64.tar.gz

Then run the tests:

    $ PATH="$PATH:$(pwd)/go/bin" poetry run pytest tests.py

If you are on Windows, you can make a pull request and let GitHub Actions run tests.
