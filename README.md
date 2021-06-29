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

To run tests, first download the langservers you need.
You can mostly read `.github/workflows/test.yml`, but the Go langserver is a bit of a gotcha.
You will need to install go from https://golang.org/,
because the one from `sudo apt install golang` is too old.
Extract it inside `tests/` so that you get a folder named `sansio-lsp-client/tests/go`.

    $ cd tests
    $ tar xf /blah/blah/Downloads/go1.16.5.linux-amd64.tar.gz

Once you have installed all langservers you want, you can run the tests:

    (env)$ PATH="$PATH:$(pwd)/tests/go/bin" poetry run pytest
