import pathlib
import platform
import shutil
import subprocess
import sys
import textwrap
import re

import pytest

import sansio_lsp_client as lsp

METHOD_DID_OPEN         = 'didOpen'
METHOD_DID_CLOSE        = 'didClose'
METHOD_DID_SAVE         = 'didSave'
METHOD_DID_CHANGE       = 'didChange'

METHOD_COMPLETION       = 'completion'
METHOD_HOVER            = 'hover'
METHOD_SIG_HELP         = 'signatureHelp'
METHOD_DEFINITION       = 'definition'
METHOD_REFERENCES       = 'references'
METHOD_IMPLEMENTATION   = 'implementation'
METHOD_DECLARATION      = 'declaration'
METHOD_TYPEDEF          = 'typeDefinition'
METHOD_DOC_SYMBOLS      = 'documentSymbol'
METHOD_FORMAT_DOC       = 'formatting'
METHOD_FORMAT_SEL       = 'rangeFormatting'

def get_meth_text_pos(text, method):
    """ searches for line: `<code> #<method>-<shift>`
          - example: `sys.getdefaultencoding() #{METHOD_HOVER}-5`
            position returned will be 5 chars before `#...`: `sys.getdefaultencodi | ng() `
        returns (x,y)
    """
    meth_mark = '#'+method
    lines = text.splitlines()

    # line index
    target_line_ind = next(i for i,line in enumerate(lines)  if meth_mark in line)
    # char index
    mark_character_ind = lines[target_line_ind].index(meth_mark)
    m = re.search(f'\\#{method}-(\\d+)', text)
    target_character_ind = mark_character_ind - int(m.group(1))

    return (target_character_ind, target_line_ind)


def start_server(command, project_root):
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

        yield (lsp_client, project_root, make_event_iterator())


@pytest.fixture(scope='session')
def server_pyls(tmp_path_factory):
    project_root = tmp_path_factory.mktemp('tmp_pyls')
    command = [sys.executable, "-m", "pyls"]

    yield from start_server(command, project_root)


test_langservers = pathlib.Path(__name__).absolute().parent / "test_langservers"


@pytest.fixture(scope='session')
def server_js(tmp_path_factory):
    project_root = tmp_path_factory.mktemp('tmp_js')
    command = [test_langservers / "node_modules/.bin/javascript-typescript-stdio"]

    yield from start_server(command, project_root)


@pytest.fixture(scope='session')
def server_clangd_10(tmp_path_factory):
    project_root = tmp_path_factory.mktemp('tmp_clangd_10')
    command = [next(test_langservers.glob("clangd_10.*")) / "bin" / "clangd"]

    yield from start_server(command, project_root)


@pytest.fixture(scope='session')
def server_clangd_11(tmp_path_factory):
    project_root = tmp_path_factory.mktemp('tmp_clangd_11')
    command = [next(test_langservers.glob("clangd_11.*")) / "bin" / "clangd"]

    yield from start_server(command, project_root)


@pytest.fixture(scope='session')
def server_gopls(tmp_path_factory):
    project_root = tmp_path_factory.mktemp('tmp_gopls')
    command = ['gopls']

    yield from start_server(command, project_root)


def do_server_method(lsp_client, event_iter, method, text, file_uri):
    def doc_pos(): #SKIP
        x,y = get_meth_text_pos(text=text, method=method)
        return lsp.TextDocumentPosition(
            textDocument=lsp.TextDocumentIdentifier(uri=file_uri),
            position=lsp.Position(line=y, character=x),
        )

    if method == METHOD_COMPLETION:
        event_id = lsp_client.completion(
            text_document_position=doc_pos(),
            context=lsp.CompletionContext(
                triggerKind=lsp.CompletionTriggerKind.INVOKED
            ),
        )
    elif method == METHOD_HOVER:
        event_id = lsp_client.hover(text_document_position=doc_pos())

    elif method == METHOD_SIG_HELP:
        event_id = lsp_client.signatureHelp(text_document_position=doc_pos())

    elif method == METHOD_DEFINITION:
        event_id = lsp_client.definition(text_document_position=doc_pos())

    elif method == METHOD_REFERENCES:
        event_id = lsp_client.references(text_document_position=doc_pos())

    else:
        raise NotImplementedError(method)

    resp = next(event_iter)
    assert not hasattr(resp, 'message_id') or resp.message_id == event_id
    return resp


def _test_pyls(server_pyls):
    lsp_client, project_root, event_iter = server_pyls

    '!!! UNDO'
    import pprint

    text = textwrap.dedent(
        f"""\
        import sys
        def do_foo(): #{METHOD_DEFINITION}-5
            sys.getdefaultencoding() #{METHOD_HOVER}-5
        def do_bar(): #{METHOD_REFERENCES}-5
            sys.intern("hey") #{METHOD_SIG_HELP}-2

        do_ #{METHOD_COMPLETION}-1"""
    )
    filename = "foo.py"
    path = project_root / filename
    path.write_text(text)
    language_id = 'python'

    inited = next(event_iter)
    assert isinstance(inited, lsp.Initialized)
    lsp_client.did_open(
        lsp.TextDocumentItem(
            uri=path.as_uri(), languageId=language_id, text=text, version=0
        )
    )

    # Dignostics #####
    diagnostics = next(event_iter)
    assert isinstance(diagnostics, lsp.PublishDiagnostics)
    assert diagnostics.uri == path.as_uri()

    diag_msgs = [diag.message for diag in diagnostics.diagnostics]
    assert "undefined name 'do_'" in diag_msgs
    assert 'E302 expected 2 blank lines, found 0' in diag_msgs
    assert 'W292 no newline at end of file' in diag_msgs

    do_meth_params = {
        'lsp_client': lsp_client,
        'event_iter': event_iter,
        'text': text,
        'file_uri': path.as_uri(),
    }

    # Completion #####
    completions = do_server_method(**do_meth_params, method=METHOD_COMPLETION)
    assert [item.label for item in completions.completion_list.items] == [
        "do_bar()",
        "do_foo()",
    ]

    # Hover #####
    hover = do_server_method(**do_meth_params, method=METHOD_HOVER)
    assert isinstance(hover, lsp.Hover)
    assert 'getdefaultencoding() -> string\n\nReturn the current default string ' \
            'encoding used by the Unicode \nimplementation.' in hover.contents

    # signatureHelp #####
    sighelp = do_server_method(**do_meth_params, method=METHOD_SIG_HELP)
    assert isinstance(sighelp, lsp.SignatureHelp)

    assert len(sighelp.signatures) > 0
    active_sig = sighelp.signatures[sighelp.activeSignature]
    assert isinstance(active_sig, lsp.SignatureInformation)
    assert len(active_sig.parameters) > 0
    assert isinstance(active_sig.parameters[0], lsp.ParameterInformation)

    # definition #####
    definitions = do_server_method(**do_meth_params, method=METHOD_DEFINITION)
    assert isinstance(definitions, lsp.Definition)

    assert isinstance(definitions.result, lsp.Location)  or  len(definitions.result) == 1
    item = definitions.result[0] if isinstance(definitions.result, list) else definitions.result
    assert isinstance(item, (lsp.Location, lsp.LocationLink))
    if isinstance(item, lsp.Location):
        assert item.uri == path.as_uri()
        definition_line = next(i for i,line in enumerate(text.splitlines()) if METHOD_DEFINITION in line)
        assert item.range.start.line == definition_line
    else: # LocationLink
        raise NotImplementedError('pyls `LocationLink` definition results')

    # references #####
    refs = do_server_method(**do_meth_params, method=METHOD_REFERENCES)
    assert isinstance(refs, lsp.References)

    assert len(refs.result) == 1
    item = refs.result[0]
    assert isinstance(item, lsp.Location)
    ref_line = next(i for i,line in enumerate(text.splitlines()) if METHOD_REFERENCES in line)
    assert item.range.start.line == ref_line

    #print(pprint.pformat(refs, width=130))
    #assert False

    # implementation #####
    # declaration #####
    # typeDefinition #####

    # documentSymbol #####
    # formatting #####
    # rangeFormatting #####
    # workspace/symbol #####

    # prepareCallHierarchy #####


@pytest.mark.skipif(
    not (test_langservers / "node_modules/.bin/javascript-typescript-stdio").exists(),
    reason="javascript-typescript-langserver not found",
)
@pytest.mark.skipif(shutil.which("node") is None, reason="node not found in $PATH")
def _test_javascript_typescript_langserver(server_js):
    lsp_client, project_root, event_iter = server_js

    '!!! UNDO'
    import pprint

    text = textwrap.dedent(
        f"""\
        function doSomethingWithFoo(x, y) {{
            const blah = x + y;
            return asdf asdf;
        }}

        doS //#{METHOD_COMPLETION}-3"""
    )
    filename = "foo.js"
    path = project_root / filename
    path.write_text(text)
    language_id = 'javascript'

    inited = next(event_iter)
    assert isinstance(inited, lsp.Initialized)
    lsp_client.did_open(
        lsp.TextDocumentItem(
            uri=path.as_uri(), languageId=language_id, text=text, version=0
        )
    )

    # Dignostics #####
    diagnostics = next(event_iter)
    assert isinstance(diagnostics, lsp.PublishDiagnostics)
    assert diagnostics.uri == path.as_uri()

    assert [diag.message for diag in diagnostics.diagnostics] == ["';' expected."]

    do_meth_params = {
        'lsp_client': lsp_client,
        'event_iter': event_iter,
        'text': text,
        'file_uri': path.as_uri(),
    }

    # Completion #####
    completions = do_server_method(**do_meth_params, method=METHOD_COMPLETION)
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
        f"""\
        #include <stdio.h>
        void do_foo(void) {{
        }}
        int do_bar(char x, long y) {{
            short z = x + y;
        }}

        int main(void) {{ do_ //#{METHOD_COMPLETION}-3"""
    ),
    "c",
)


@clangd_decorator(10)
def _test_clangd_10(server_clangd_10):
    lsp_client, project_root, event_iter = server_clangd_10

    '!!! UNDO'
    import pprint

    filename, text, language_id = c_args
    path = project_root / filename
    path.write_text(text)

    inited = next(event_iter)
    assert isinstance(inited, lsp.Initialized)
    lsp_client.did_open(
        lsp.TextDocumentItem(
            uri=path.as_uri(), languageId=language_id, text=text, version=0
        )
    )

    # Dignostics #####
    diagnostics = next(event_iter)
    assert isinstance(diagnostics, lsp.PublishDiagnostics)
    assert diagnostics.uri == path.as_uri()

    assert [diag.message for diag in diagnostics.diagnostics] == [
        'Non-void function does not return a value',
        "Use of undeclared identifier 'do_'",
        "Expected '}'",
    ]

    do_meth_params = {
        'lsp_client': lsp_client,
        'event_iter': event_iter,
        'text': text,
        'file_uri': path.as_uri(),
    }

    # Completion #####
    completions = do_server_method(**do_meth_params, method=METHOD_COMPLETION)
    completions = [item.label for item in completions.completion_list.items]
    assert " do_foo()" in completions
    assert " do_bar(char x, long y)" in completions


@clangd_decorator(11)
def _test_clangd_11(server_clangd_11):
    lsp_client, project_root, event_iter = server_clangd_11

    '!!! UNDO'
    import pprint

    filename, text, language_id = c_args
    path = project_root / filename
    path.write_text(text)

    inited = next(event_iter)
    assert isinstance(inited, lsp.Initialized)
    lsp_client.did_open(
        lsp.TextDocumentItem(
            uri=path.as_uri(), languageId=language_id, text=text, version=0
        )
    )

    # Dignostics #####
    diagnostics = next(event_iter)
    assert isinstance(diagnostics, lsp.PublishDiagnostics)
    assert diagnostics.uri == path.as_uri()

    assert [diag.message for diag in diagnostics.diagnostics] == [
        'Non-void function does not return a value',
        "Use of undeclared identifier 'do_'",
        "Expected '}'",
    ]

    do_meth_params = {
        'lsp_client': lsp_client,
        'event_iter': event_iter,
        'text': text,
        'file_uri': path.as_uri(),
    }

    # Completion #####
    completions = do_server_method(**do_meth_params, method=METHOD_COMPLETION)
    completions = [item.label for item in completions.completion_list.items]
    assert " do_foo()" in completions
    assert " do_bar(char x, long y)" in completions




'!!! rork'
def test_gopls(server_gopls):
    lsp_client, project_root, event_iter = server_gopls

    '!!! UNDO'
    import pprint

    text = textwrap.dedent(
        f"""\
        package main

        import "fmt"

        func doSomethingWithFoo(x, y) {{
            blah := x + y
            return asdf asdf
        }}

        doS //#{METHOD_COMPLETION}-3"""
    )
    filename = "foo.js"
    path = project_root / filename
    path.write_text(text)
    language_id = 'javascript'

    inited = next(event_iter)
    assert isinstance(inited, lsp.Initialized)
    lsp_client.did_open(
        lsp.TextDocumentItem(
            uri=path.as_uri(), languageId=language_id, text=text, version=0
        )
    )

    # Dignostics #####
    diagnostics = next(event_iter)
    assert isinstance(diagnostics, lsp.PublishDiagnostics)
    assert diagnostics.uri == path.as_uri()

    print('\n diag', pprint.pformat(diagnostics, width=130))

    #assert [diag.message for diag in diagnostics.diagnostics] == ["';' expected."]

    do_meth_params = {
        'lsp_client': lsp_client,
        'event_iter': event_iter,
        'text': text,
        'file_uri': path.as_uri(),
    }

    # Completion #####
    completions = do_server_method(**do_meth_params, method=METHOD_COMPLETION)

    print('\n compl', pprint.pformat(refs, width=130))

    assert "doSomethingWithFoo" in [
        item.label for item in completions.completion_list.items
    ]


