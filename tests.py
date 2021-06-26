import contextlib
import functools
import pprint
import pathlib
import platform
import shutil
import subprocess
import sys
import textwrap
import re
import threading
import queue
import time

import pytest

import sansio_lsp_client as lsp


METHOD_COMPLETION = "completion"
METHOD_HOVER = "hover"
METHOD_SIG_HELP = "signatureHelp"
METHOD_DEFINITION = "definition"
METHOD_REFERENCES = "references"
METHOD_IMPLEMENTATION = "implementation"
METHOD_DECLARATION = "declaration"
METHOD_TYPEDEF = "typeDefinition"
METHOD_DOC_SYMBOLS = "documentSymbol"
METHOD_FORMAT_DOC = "formatting"
METHOD_FORMAT_SEL = "rangeFormatting"

RESPONSE_TYPES = {
    METHOD_COMPLETION: lsp.Completion,
    METHOD_HOVER: lsp.Hover,
    METHOD_SIG_HELP: lsp.SignatureHelp,
    METHOD_DEFINITION: lsp.Definition,
    METHOD_REFERENCES: lsp.References,
    METHOD_IMPLEMENTATION: lsp.Implementation,
    METHOD_DECLARATION: lsp.Declaration,
    METHOD_TYPEDEF: lsp.TypeDefinition,
    METHOD_DOC_SYMBOLS: lsp.MDocumentSymbols,
    METHOD_FORMAT_DOC: lsp.DocumentFormatting,
    METHOD_FORMAT_SEL: lsp.DocumentFormatting,
}


def get_meth_text_pos(text, method):
    """ searches for line: `<code> #<method>-<shift>`
          - example: `sys.getdefaultencoding() #{METHOD_HOVER}-5`
            position returned will be 5 chars before `#...`: `sys.getdefaultencodi | ng() `
        returns (x,y)
    """
    meth_mark = "#" + method
    lines = text.splitlines()

    # line index
    target_line_ind = next(i for i, line in enumerate(lines) if meth_mark in line)
    # char index
    mark_character_ind = lines[target_line_ind].index(meth_mark)
    m = re.search(f"\\#{method}-(\\d+)", text)
    target_character_ind = mark_character_ind - int(m.group(1))

    return (target_character_ind, target_line_ind)


class ThreadedServer:
    """ Gathers all messages received from server - to handle random-order-messages \
            that are not a response to a request.

        * get_msg_by_type() - get server message by type. waits for the message
        * stop()            - stop server via LSP
    """

    def __init__(self, process, root_uri):
        self.process = process
        self.root_uri = root_uri
        self.lsp_client = lsp.Client(
            root_uri=root_uri,
            workspace_folders=[lsp.WorkspaceFolder(uri=self.root_uri, name="Root")],
            trace="verbose",
        )
        self.msgs = []

        self._pout = process.stdout
        self._pin = process.stdin

        self._read_q = queue.Queue()
        self._send_q = queue.Queue()

        self.reader_thread = threading.Thread(
            target=self._read_loop, name="lsp-reader", daemon=True
        )
        self.writer_thread = threading.Thread(
            target=self._send_loop, name="lsp-writer", daemon=True
        )

        self.reader_thread.start()
        self.writer_thread.start()

        self.exception = None

    @property
    def all_msgs(self):
        return self.msgs[:]

    # threaded
    def _read_loop(self):
        try:
            while self._pout:
                data = self._pout.read(1)

                if data == b"":
                    break

                self._read_q.put(data)
        except Exception as ex:
            self.exception = ex
        self._send_q.put_nowait(None)  # stop send_loop()

    # threaded
    def _send_loop(self):
        try:
            while self._pin:
                buf = self._send_q.get()

                if buf is None:
                    break

                # print(f"\nsending: {buf}\n")

                self._pin.write(buf)
                self._pin.flush()
        except Exception as ex:
            self.exception = ex

    def _queue_data_to_send(self):
        send_buf = self.lsp_client.send()
        if send_buf:
            self._send_q.put(send_buf)

    def _read_data_received(self):
        while not self._read_q.empty():
            data = self._read_q.get()
            events = self.lsp_client.recv(data)
            for ev in events:
                self.msgs.append(ev)
                self._try_default_reply(ev)

    def _try_default_reply(self, msg):
        empty_reply_classes = (
            lsp.ShowMessageRequest,
            lsp.WorkDoneProgressCreate,
            lsp.RegisterCapabilityRequest,
            lsp.ConfigurationRequest,
        )

        if isinstance(msg, empty_reply_classes):
            msg.reply()

        elif isinstance(msg, lsp.WorkspaceFolders):
            msg.reply([lsp.WorkspaceFolder(uri=self.root_uri, name="Root")])

        else:
            print(f"Can't autoreply: {type(msg)}")

    def _process_qs(self):
        self._queue_data_to_send()
        self._read_data_received()

    def get_msg_by_type(self, _type, timeout=5):
        end_time = time.time() + timeout
        while time.time() < end_time:
            self._process_qs()

            # raise thread's exception if have any
            if self.exception:
                raise self.exception

            for msg in self.msgs:
                if isinstance(msg, _type):
                    self.msgs.remove(msg)
                    return msg

            time.sleep(0.2)
        # end while

        raise Exception(
            f"Didn`t receive {_type} in time; have: " + pprint.pprint(self.msgs)
        )

    def stop(self):
        if self.lsp_client.is_initialized:
            self.lsp_client.shutdown()  # send shutdown...
            self.get_msg_by_type(lsp.Shutdown)  # receive shutdown...
            self.lsp_client.exit()  # send exit...
            self._process_qs()  # give data to send-thread
        else:
            self.process.kill()


test_langservers = pathlib.Path(__file__).absolute().parent / "test_langservers"


SERVER_PYLS = "pyls"
SERVER_JS = "js"
SERVER_CLANGD_10 = "clangd_10"
SERVER_CLANGD_11 = "clangd_11"
SERVER_GOPLS = "gopls"

SERVER_COMMANDS = {
    SERVER_PYLS: lambda: [sys.executable, "-m", "pyls"],
    SERVER_JS: lambda: [
        test_langservers / "node_modules/.bin/javascript-typescript-stdio"
    ],
    SERVER_CLANGD_10: lambda: [
        next(test_langservers.glob("clangd_10.*")) / "bin" / "clangd"
    ],
    SERVER_CLANGD_11: lambda: [
        next(test_langservers.glob("clangd_11.*")) / "bin" / "clangd"
    ],
    SERVER_GOPLS: lambda: [test_langservers / "bin" / "gopls"],
}


@contextlib.contextmanager
def start_server(langserver_name, tmp_path_factory):
    command = SERVER_COMMANDS[langserver_name]
    command = command()
    project_root = tmp_path_factory.mktemp("tmp_" + langserver_name)

    if langserver_name == SERVER_GOPLS:
        # create file(s) before starting server, jic
        for fn, text in files_go.items():
            path = project_root / fn
            path.write_text(text)

    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )
    tserver = ThreadedServer(process, project_root.as_uri())

    try:
        yield (tserver, project_root)
    except Exception as e:
        # Prevent freezing tests
        process.kill()
        raise e

    if tserver.msgs:
        print(
            "* unprocessed messages:",
            ", ".join(type(m).__name__ for m in tserver.msgs),
        )

    tserver.stop()


def do_server_method(tserver, text, file_uri, method, response_type=None):
    def doc_pos():  # SKIP
        x, y = get_meth_text_pos(text=text, method=method)
        return lsp.TextDocumentPosition(
            textDocument=lsp.TextDocumentIdentifier(uri=file_uri),
            position=lsp.Position(line=y, character=x),
        )

    if not response_type:
        response_type = RESPONSE_TYPES[method]

    if method == METHOD_COMPLETION:
        event_id = tserver.lsp_client.completion(
            text_document_position=doc_pos(),
            context=lsp.CompletionContext(
                triggerKind=lsp.CompletionTriggerKind.INVOKED
            ),
        )
    elif method == METHOD_HOVER:
        event_id = tserver.lsp_client.hover(text_document_position=doc_pos())

    elif method == METHOD_SIG_HELP:
        event_id = tserver.lsp_client.signatureHelp(text_document_position=doc_pos())

    elif method == METHOD_DEFINITION:
        event_id = tserver.lsp_client.definition(text_document_position=doc_pos())

    elif method == METHOD_REFERENCES:
        event_id = tserver.lsp_client.references(text_document_position=doc_pos())

    elif method == METHOD_IMPLEMENTATION:
        event_id = tserver.lsp_client.implementation(text_document_position=doc_pos())

    elif method == METHOD_DECLARATION:
        event_id = tserver.lsp_client.declaration(text_document_position=doc_pos())

    elif method == METHOD_TYPEDEF:
        event_id = tserver.lsp_client.typeDefinition(text_document_position=doc_pos())

    elif method == METHOD_DOC_SYMBOLS:
        _docid = lsp.TextDocumentIdentifier(uri=file_uri)
        event_id = tserver.lsp_client.documentSymbol(text_document=_docid)

    else:
        raise NotImplementedError(method)

    # "blocking" -- will wait for message
    resp = tserver.get_msg_by_type(response_type)
    assert not hasattr(resp, "message_id") or resp.message_id == event_id
    return resp


c_args = (
    "foo.c",
    textwrap.dedent(
        f"""\
        #include <stdio.h>
        void do_foo(void);
        void do_foo(void) {{//#{METHOD_DECLARATION}-13
        }}
        int do_bar(char x, long y) {{
            short z = x + y;
        }}

        int main(void) {{ do_ //#{METHOD_COMPLETION}-3"""
    ),
    "c",
)
files_go = {
    "foo.go": textwrap.dedent(
        f"""\
        package main

        import "fmt"

        type Creature struct {{
            Name string
        }}
        func (c*Creature) Dump() {{
            fmt.Printf("Name: '%s'", c.Name)
        }}

        func doSomethingWithFoo(x, y) string {{
            blah := x + y
            cat := &Creature{{"cat"}} //#{METHOD_TYPEDEF}-18
            cat := &Creature{{"cat"}} //#{METHOD_IMPLEMENTATION}-14
            cat.Dump() //#{METHOD_IMPLEMENTATION}-7
            return asdf asdf
        }}
        var s1 = doS //#{METHOD_COMPLETION}-3"""
    ),
    "go.mod": textwrap.dedent(
        """\
        module example.com/hellp

        go 1.10
        """
    ),
}


def check_that_langserver_works(langserver_name, tmp_path_factory):
    with start_server(langserver_name, tmp_path_factory) as (tserver, project_root):
        if langserver_name == "pyls":
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
            language_id = "python"

        elif langserver_name == "js":
            text = textwrap.dedent(
                f"""\
                function doSomethingWithFoo(x, y) {{
                    const blah = x + y;
                    return asdf asdf;
                }}

                doS //#{METHOD_COMPLETION}-3"""
            )
            filename = "foo.js"
            language_id = "javascript"

        elif langserver_name in ("clangd_10", "clangd_11"):
            filename, text, language_id = c_args

        elif langserver_name == "gopls":
            language_id = "go"
            [filename] = [fn for fn in files_go if fn.endswith(".go")]
            text = files_go[filename]
        else:
            raise ValueError(langserver_name)

        path = project_root / filename
        path.write_text(text)

        # Initialized #####
        tserver.get_msg_by_type(lsp.Initialized)
        tserver.lsp_client.did_open(
            lsp.TextDocumentItem(
                uri=path.as_uri(), languageId=language_id, text=text, version=0
            )
        )

        # Diagnostics #####
        diagnostics = tserver.get_msg_by_type(lsp.PublishDiagnostics)
        assert diagnostics.uri == path.as_uri()
        diag_msgs = [diag.message for diag in diagnostics.diagnostics]

        if langserver_name == "pyls":
            assert "undefined name 'do_'" in diag_msgs
            assert "E302 expected 2 blank lines, found 0" in diag_msgs
            assert "W292 no newline at end of file" in diag_msgs
        elif langserver_name == "js":
            assert diag_msgs == [
                "';' expected."
            ]
        elif langserver_name in ("clangd_10", "clangd_11"):
            assert diag_msgs == [
                "Non-void function does not return a value",
                "Use of undeclared identifier 'do_'",
                "Expected '}'",
            ]
        elif langserver_name == "gopls":
            assert diag_msgs == [
                "expected ';', found asdf"
            ]
        else:
            raise ValueError(langserver_name)

        do_method = functools.partial(do_server_method, tserver, text, path.as_uri())

        # Completions #####
        completions = do_method(METHOD_COMPLETION)
        completion_labels = [item.label for item in completions.completion_list.items]

        if langserver_name == "pyls":
            assert completion_labels == [
                "do_bar()",
                "do_foo()"
            ]
        elif langserver_name in ("js", "gopls"):
            assert "doSomethingWithFoo" in completion_labels
        elif langserver_name in ("clangd_10", "clangd_11"):
            assert " do_foo()" in completion_labels
            assert " do_bar(char x, long y)" in completion_labels
        else:
            raise ValueError(langserver_name)

        # Other #####

        if langserver_name == "pyls":
            # Hover #####
            hover = do_method(METHOD_HOVER)
            # NOTE: crude because response changes from one Python version to another
            assert "getdefaultencoding() -> str" in str(hover.contents)

            # signatureHelp #####
            sighelp = do_method(METHOD_SIG_HELP)

            assert len(sighelp.signatures) > 0
            active_sig = sighelp.signatures[sighelp.activeSignature]
            assert isinstance(active_sig, lsp.SignatureInformation)
            assert len(active_sig.parameters) > 0
            assert isinstance(active_sig.parameters[0], lsp.ParameterInformation)

            # definition #####
            definitions = do_method(METHOD_DEFINITION)

            assert (
                isinstance(definitions.result, lsp.Location)
                or len(definitions.result) == 1
            )
            item = (
                definitions.result[0]
                if isinstance(definitions.result, list)
                else definitions.result
            )
            assert isinstance(item, (lsp.Location, lsp.LocationLink))
            if isinstance(item, lsp.Location):
                assert item.uri == path.as_uri()
                definition_line = next(
                    i
                    for i, line in enumerate(text.splitlines())
                    if METHOD_DEFINITION in line
                )
                assert item.range.start.line == definition_line
            else:  # LocationLink
                raise NotImplementedError("pyls `LocationLink` definition results")

            # references #####
            refs = do_method(METHOD_REFERENCES)

            assert len(refs.result) == 1
            item = refs.result[0]
            assert isinstance(item, lsp.Location)
            ref_line = next(
                i
                for i, line in enumerate(text.splitlines())
                if METHOD_REFERENCES in line
            )
            assert item.range.start.line == ref_line

            # documentSymbol #####
            doc_symbols = do_method(METHOD_DOC_SYMBOLS)
            assert len(doc_symbols.result) == 3
            symb_names = {s.name for s in doc_symbols.result}
            assert symb_names == {"sys", "do_foo", "do_bar"}

            # formatting #####
            tserver.lsp_client.formatting(
                text_document=lsp.TextDocumentIdentifier(uri=path.as_uri()),
                options=lsp.FormattingOptions(tabSize=4, insertSpaces=True),
            )
            formatting = tserver.get_msg_by_type(RESPONSE_TYPES[METHOD_FORMAT_DOC])
            assert formatting.result

            # Error -- method not supported by server #####
            tserver.lsp_client.workspace_symbol()
            err = tserver.get_msg_by_type(lsp.ResponseError)
            assert err.message == "Method Not Found: workspace/symbol"

        if langserver_name == "clangd_11":  # TODO: would this work for clangd 10?
            # workspace/symbol #####
            # TODO - empty for some reason
            # tserver.lsp_client.workspace_symbol()
            # w_symb = tserver.get_msg_by_type(lsp.MWorkspaceSymbols)

            # declaration #####
            declaration = do_method(METHOD_DECLARATION)
            assert len(declaration.result) == 1
            assert declaration.result[0].uri == path.as_uri()

        if langserver_name == "gopls":
            # implementation #####
            # TODO - null result for some reason
            # implementation = do_method(METHOD_IMPLEMENTATION)
            # print(f' implementation: {implementation}')

            # typeDefinition #####
            typedef = do_method(METHOD_TYPEDEF)
            assert len(typedef.result) == 1
            assert typedef.result[0].uri == path.as_uri()


_skip_windows_clangd = pytest.mark.skipif(
    platform.system() == "Windows", reason="don't know how clangd works on windows"
)


def _needs_clangd(version):
    return pytest.mark.skipif(
        not list(test_langservers.glob(f"clangd_{version}.*")),
        reason=f"clangd {version} not found",
    )


def test_pyls(tmp_path_factory):
    check_that_langserver_works("pyls", tmp_path_factory)


@pytest.mark.skipif(
    not (test_langservers / "node_modules/.bin/javascript-typescript-stdio").exists(),
    reason="javascript-typescript-langserver not found",
)
@pytest.mark.skipif(shutil.which("node") is None, reason="node not found in $PATH")
def test_javascript_typescript_langserver(tmp_path_factory):
    check_that_langserver_works("js", tmp_path_factory)


@_skip_windows_clangd
@_needs_clangd(10)
def test_clangd_10(tmp_path_factory):
    check_that_langserver_works("clangd_10", tmp_path_factory)


@_skip_windows_clangd
@_needs_clangd(11)
def test_clangd_11(tmp_path_factory):
    check_that_langserver_works("clangd_11", tmp_path_factory)


@pytest.mark.skipif(
    not (test_langservers / "bin" / "gopls").exists(),
    reason="gopls not installed in test_langservers/",
)
def test_gopls(tmp_path_factory):
    check_that_langserver_works("gopls", tmp_path_factory)
