import contextlib
import pathlib
import shutil
import subprocess
import sys

import pytest

import sansio_lsp_client as lsp


@contextlib.contextmanager
def run_langserver(project_root, command):
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE
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


def do_stuff_with_a_langserver(
    tmp_path, filename, file_content, command, cwd=None
):
    path = tmp_path / filename
    path.write_text(file_content)

    with run_langserver(tmp_path, command) as (lsp_client, event_iter):
        inited = next(event_iter)
        assert isinstance(inited, lsp.Initialized)
        lsp_client.did_open(
            lsp.TextDocumentItem(
                uri=path.as_uri(),
                languageId="python",
                text=file_content,
                version=0,
            )
        )

        diagnostics = next(event_iter)
        assert isinstance(diagnostics, lsp.PublishDiagnostics)
        assert diagnostics.uri == path.as_uri()

        event_id = lsp_client.completions(
            text_document_position=lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=path.as_uri()),
                position=lsp.Position(
                    # first line = 0, first column = 0
                    line=file_content.count("\n"),
                    character=len(file_content.split("\n")[-1]),
                ),
            ),
            context=lsp.CompletionContext(
                triggerKind=lsp.CompletionTriggerKind.INVOKED
            ),
        )
        completions = next(event_iter)
        assert completions.message_id == event_id

        return (diagnostics, completions)


def test_pyls(tmp_path):
    diagnostics, completions = do_stuff_with_a_langserver(
        tmp_path,
        "foo.py",
        """\
import sys
def do_foo():
    pass
def do_bar():
    pass

do_""",
        [sys.executable, "-m", "pyls"],
    )

    assert [diag.message for diag in diagnostics.diagnostics] == [
        "'sys' imported but unused",
        "undefined name 'do_'",
        "E302 expected 2 blank lines, found 0",
        "E302 expected 2 blank lines, found 0",
        "W292 no newline at end of file",
        "E305 expected 2 blank lines after class or function definition, found 1",
    ]

    assert [item.label for item in completions.completion_list.items] == [
        "do_bar()",
        "do_foo()",
    ]


jstsls_path = pathlib.Path(__name__).absolute().parent / "jsts-langserver"


@pytest.mark.skipif(
    not jstsls_path.exists(),
    reason=f"javascript-typescript-langserver not installed into {jstsls_path}",
)
@pytest.mark.skipif(
    shutil.which("node") is None, reason="node not found in $PATH"
)
def test_javascript_typescript_langserver(tmp_path):
    diagnostics, completions = do_stuff_with_a_langserver(
        tmp_path,
        "foo.js",
        """\
const blah = require("asdf");
function doSomethingWithFoo() {
}
function doSomethingWithBar() {
}

doS""",
        [jstsls_path / "node_modules/.bin/javascript-typescript-stdio"],
    )
    assert not diagnostics.diagnostics
    assert [item.label for item in completions.completion_list.items[:2]] == [
        "doSomethingWithFoo",
        "doSomethingWithBar",
    ]
