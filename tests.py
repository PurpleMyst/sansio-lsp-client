import contextlib
import pathlib
import platform
import shutil
import subprocess
import sys
import textwrap

import pytest

import sansio_lsp_client as lsp


@contextlib.contextmanager
def run_langserver(project_root, command):
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    ) as process:
        lsp_client = lsp.Client(trace="verbose", root_uri=project_root.as_uri())

        def make_event_iterator():
            while True:
                process.stdin.write(lsp_client.send())
                process.stdin.flush()
                # TODO: multiple bytes not work
                received = process.stdout.read(1)
                assert received
                yield from lsp_client.recv(received)

        yield (lsp_client, make_event_iterator())


def do_stuff_with_a_langserver(tmp_path, filename, file_content, language_id, command):
    path = tmp_path / filename
    path.write_text(file_content)

    with run_langserver(tmp_path, command) as (lsp_client, event_iter):
        inited = next(event_iter)
        assert isinstance(inited, lsp.Initialized)
        lsp_client.did_open(
            lsp.TextDocumentItem(
                uri=path.as_uri(), languageId=language_id, text=file_content, version=0
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
        textwrap.dedent(
            """\
            import sys
            def do_foo():
                pass
            def do_bar():
                pass

            do_"""
        ),
        "python",
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


test_langservers = pathlib.Path(__name__).absolute().parent / "test_langservers"


@pytest.mark.skipif(
    not (test_langservers / "node_modules/.bin/javascript-typescript-stdio").exists(),
    reason="javascript-typescript-langserver not found",
)
@pytest.mark.skipif(shutil.which("node") is None, reason="node not found in $PATH")
def test_javascript_typescript_langserver(tmp_path):
    diagnostics, completions = do_stuff_with_a_langserver(
        tmp_path,
        "foo.js",
        textwrap.dedent(
            """\
            function doSomethingWithFoo(x, y) {
                const blah = x + y;
                return asdf asdf;
            }

            doS"""
        ),
        "javascript",
        [test_langservers / "node_modules/.bin/javascript-typescript-stdio"],
    )
    assert [diag.message for diag in diagnostics.diagnostics] == ["';' expected."]
    assert "doSomethingWithFoo" in [
        item.label for item in completions.completion_list.items
    ]


def clangd_decorator(version):
    def inner(function):
        function = pytest.mark.skipif(
            platform.system() == "Windows",
            reason="don't know how clangd works on windows",
        )(function)
        function = pytest.mark.skipif(
            not list(test_langservers.glob(f"clangd_{version}.*")),
            reason=f"clangd {version} not found",
        )(function)
        return function

    return inner


c_args = (
    "foo.c",
    textwrap.dedent(
        """\
        #include <stdio.h>
        void do_foo(void) {
        }
        int do_bar(char x, long y) {
            short z = x + y;
        }

        int main(void) { do_"""
    ),
    "c",
)


@clangd_decorator(10)
def test_clangd_10(tmp_path):
    diagnostics, completions = do_stuff_with_a_langserver(
        tmp_path,
        *c_args,
        [next(test_langservers.glob("clangd_10.*")) / "bin" / "clangd"],
    )
    assert [diag.message for diag in diagnostics.diagnostics] == [
        "Non-void function does not return a value",
        "Use of undeclared identifier 'do_'",
        "Expected '}'\n\nfoo.c:8:16: note: to match this '{'",
        "To match this '{'\n\nfoo.c:8:21: error: expected '}'",
    ]
    assert [item.label for item in completions.completion_list.items] == [
        " do_bar(char x, long y)",
        " do_foo()",
        "•__STDC_IEC_559_COMPLEX__",
        "•__STDC_ISO_10646__",
    ]


@clangd_decorator(11)
def test_clangd_11(tmp_path):
    diagnostics, completions = do_stuff_with_a_langserver(
        tmp_path,
        *c_args,
        [next(test_langservers.glob("clangd_11.*")) / "bin" / "clangd"],
    )
    assert [diag.message for diag in diagnostics.diagnostics] == [
        "Non-void function does not return a value",
        "Use of undeclared identifier 'do_'",
        "Expected '}'\n\nfoo.c:8:16: note: to match this '{'",
        "To match this '{'\n\nfoo.c:8:21: error: expected '}'",
    ]
    assert [item.label for item in completions.completion_list.items] == [
        " do_bar(char x, long y)",
        " do_foo()",
        "•__STDC_IEC_559_COMPLEX__",
        "•__STDC_ISO_10646__",
    ]
