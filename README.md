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

Most tests don't work on Windows,
but GitHub Actions runs tests of all pull requests and uploads coverage files from them.
TODO: add instructions for looking at coverage files on Windows

To run tests, first download the langservers you need by reading `.github/workflows/test.yml`.
Then run the tests:

    $ PATH="$PATH:$(pwd)/tests/go/bin" poetry run pytest
