import contextlib
import pathlib
import subprocess
import sys

import pytest

import sansio_lsp_client as lsp


@contextlib.contextmanager
def run_stdio_langserver(project_root, command, **popen_kwargs):
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, **popen_kwargs
    ) as process:
        lsp_client = lsp.Client(
            trace="verbose", root_uri=project_root.as_uri()
        )

        def make_event_iterator():
            while True:
                process.stdin.write(lsp_client.send())
                process.stdin.flush()
                # TODO: multiple bytes not work
                received = process.stdout.read(1)
                assert received
                yield from lsp_client.recv(received)

        yield (lsp_client, make_event_iterator())


def test_pyls(tmp_path):
    foo_uri = (tmp_path / "foo.py").as_uri()

    with run_stdio_langserver(tmp_path, [sys.executable, "-m", "pyls"]) as (
        lsp_client,
        event_iter,
    ):
        inited = next(event_iter)
        assert isinstance(inited, lsp.Initialized)
        lsp_client.did_open(
            lsp.TextDocumentItem(
                uri=foo_uri,
                languageId="python",
                text="""\
import sys
def do_foo():
    pass
def do_bar():
    pass

do_""",
                version=0,
            )
        )

        diagnostics = next(event_iter)
        assert isinstance(diagnostics, lsp.PublishDiagnostics)
        assert diagnostics.uri == foo_uri
        assert [diag.message for diag in diagnostics.diagnostics] == [
            "'sys' imported but unused",
            "undefined name 'do_'",
            "E302 expected 2 blank lines, found 0",
            "E302 expected 2 blank lines, found 0",
            "W292 no newline at end of file",
            "E305 expected 2 blank lines after class or function definition, found 1",
        ]

        event_id = lsp_client.completions(
            text_document_position=lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=foo_uri),
                position=lsp.Position(line=6, character=3),
            ),
            context=lsp.CompletionContext(
                triggerKind=lsp.CompletionTriggerKind.INVOKED
            ),
        )
        completion = next(event_iter)
        assert completion.message_id == event_id
        assert [item.label for item in completion.completion_list.items] == [
            "do_bar()",
            "do_foo()",
        ]


jstsls_path = pathlib.Path(__name__).absolute().parent / 'jsts-langserver'


@pytest.mark.skipif(
    not jstsls_path.exists(),
    reason=f"javascript-typescript-langserver not installed into {jstsls_path}"
)
def test_javascript_typescript_langserver(tmp_path):
    foo_path = tmp_path / "foo.js"
    foo_path.write_text("""\
const blah = require("asdf");
function doSomethingWithFoo() {
}
function doSomethingWithBar() {
}

doS""")

    with run_stdio_langserver(
        tmp_path, [jstsls_path / 'node_modules' / '.bin' / 'javascript-typescript-stdio'], cwd=tmp_path
    ) as (lsp_client, event_iter):
        inited = next(event_iter)
        assert isinstance(inited, lsp.Initialized)
        lsp_client.did_open(
            lsp.TextDocumentItem(
                uri=foo_path.as_uri(),
                languageId="javascript",
                text=foo_path.read_text(),
                version=0,
            )
        )

        diagnostics = next(event_iter)
        assert isinstance(diagnostics, lsp.PublishDiagnostics)
        assert diagnostics.uri == foo_path.as_uri()
        assert [diag.message for diag in diagnostics.diagnostics] == []

        event_id = lsp_client.completions(
            text_document_position=lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=foo_path.as_uri()),
                position=lsp.Position(line=6, character=3),
            ),
            context=lsp.CompletionContext(
                triggerKind=lsp.CompletionTriggerKind.INVOKED
            ),
        )
        completion = next(event_iter)
        assert completion.message_id == event_id
        assert [item.label for item in completion.completion_list.items[:2]] == [
            "doSomethingWithFoo",
            "doSomethingWithBar",
        ]
