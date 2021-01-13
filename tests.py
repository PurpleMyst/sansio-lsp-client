import contextlib
import subprocess
import sys

import sansio_lsp_client as lsp


@contextlib.contextmanager
def run_stdio_langserver(project_root, command):
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
