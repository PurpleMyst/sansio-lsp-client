# sansio-lsp-client

This is an implementation of the client side of the langserver (LSP) protocol, useful for embedding
easily in your editor.
It is used in [Porcupine](https://github.com/Akuli/porcupine),
and will soon be used in [Biscuit](https://github.com/billyeatcookies/Biscuit) too.

The "sans io" part of the name means "without IO".
It means that this library doesn't do IO, and you do it instead.
Specifically:
- You start a langserver process
- You read data from the stdout of the langserver process
- You feed the data to this library
- This library returns data to be written to the stdin of the langserver process
- You write the data to the stdin of the langserver process.

This way, this library is very flexible.
It assumes nothing about how IO works,
so you can use it with threads, without threads, with sync code, with async code,
or with any other kind of IO thing.


## Usage

Unfortunately, there isn't much documentation. Hopefully someone will write some docs eventually :)

If you want to add langserver support to a text editor, you could look at
[Porcupine's langserver plugin](https://github.com/Akuli/porcupine/blob/main/porcupine/plugins/langserver.py)
to get started. Porcupine is MIT licensed, so you can use its code in your projects as long as you credit Porcupine accordingly.
You can also look at [this project's tests](tests/), which are simple in principle, but kind of messy in practice.


## Maintenance Status

Currently (2024) there are two maintainers (Akuli and PurpleMyst) who merge and review pull requests.
Also, the project cannot become totally broken, because Akuli uses Porcupine almost every day,
and langserver support is an essential part of Porcupine.

New features are usually added by someone else than the two maintainers.
We recommend just adding what you need for your use case and making a pull request.


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
Extract it inside where you cloned `sansio-lsp-client`
so that you get an executable named `sansio-lsp-client/go/bin/go`.

    $ tar xf ~/Downloads/go1.16.5.linux-amd64.tar.gz

Once you have installed all langservers you want, you can run the tests:

    (env)$ PATH="$PATH:$(pwd)/go/bin" poetry run pytest -v
