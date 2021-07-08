import contextlib
import functools
import pprint
import pathlib
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


# TODO: More stuff coming from halfbrained pull requests
METHOD_COMPLETION = "completion"
RESPONSE_TYPES = {METHOD_COMPLETION: lsp.Completion}


def get_meth_text_pos(text, method):
    """ searches for line: `<code> #<method>-<shift>`
          - example: `sys.getdefaultencoding()
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
    """
    Gathers all messages received from server - to handle random-order-messages
    that are not a response to a request.
    """

    def __init__(self, process, root_uri):
        self.process = process
        self.root_uri = root_uri
        self.lsp_client = lsp.Client(root_uri=root_uri, trace="verbose")
        self.lsp_client._recv_catches_and_logs_errors = False
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

    # threaded
    def _read_loop(self):
        try:
            while True:
                data = self.process.stdout.read(1)

                if data == b"":
                    break

                self._read_q.put(data)
        except Exception as ex:
            self.exception = ex
        self._send_q.put_nowait(None)  # stop send loop

    # threaded
    def _send_loop(self):
        try:
            while True:
                chunk = self._send_q.get()
                if chunk is None:
                    break

                # print(f"\nsending: {buf}\n")
                self.process.stdin.write(chunk)
                self.process.stdin.flush()
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
        if isinstance(msg, lsp.ShowMessageRequest):
            msg.reply()

    def wait_for_message_of_type(self, type_, timeout=5):
        end_time = time.time() + timeout
        while time.time() < end_time:
            self._queue_data_to_send()
            self._read_data_received()

            # raise thread's exception if have any
            if self.exception:
                raise self.exception

            for msg in self.msgs:
                if isinstance(msg, type_):
                    self.msgs.remove(msg)
                    return msg

            time.sleep(0.2)

        raise Exception(
            f"Didn't receive {type_} in time; have: " + pprint.pformat(self.msgs)
        )

    def exit_cleanly(self):
        #        if self.msgs:
        #            # Not necessarily error, gopls sends logging messages for example
        #            print(
        #                "* unprocessed messages: " + pprint.pformat(self.msgs)
        #            )

        assert self.lsp_client.state != lsp.ClientState.NOT_INITIALIZED
        assert self.lsp_client.state != lsp.ClientState.WAITING_FOR_INITIALIZED
        self.lsp_client.shutdown()
        self.wait_for_message_of_type(lsp.Shutdown)
        self.lsp_client.exit()
        self._queue_data_to_send()
        self._read_data_received()

    def do_method(self, text, file_uri, method, response_type=None):
        def doc_pos():
            x, y = get_meth_text_pos(text=text, method=method)
            return lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=file_uri),
                position=lsp.Position(line=y, character=x),
            )

        if not response_type:
            response_type = RESPONSE_TYPES[method]

        if method == METHOD_COMPLETION:
            event_id = self.lsp_client.completions(
                text_document_position=doc_pos(),
                context=lsp.CompletionContext(
                    triggerKind=lsp.CompletionTriggerKind.INVOKED
                ),
            )
        else:
            raise NotImplementedError(method)

        resp = self.wait_for_message_of_type(response_type)
        assert not hasattr(resp, "message_id") or resp.message_id == event_id
        return resp


langserver_dir = pathlib.Path(__file__).absolute().parent / "langservers"


_clangd_10 = next(langserver_dir.glob("clangd_10.*/bin/clangd"), None)
_clangd_11 = next(langserver_dir.glob("clangd_11.*/bin/clangd"), None)
SERVER_COMMANDS = {
    "pyls": [sys.executable, "-m", "pyls"],
    "js": [langserver_dir / "node_modules/.bin/javascript-typescript-stdio"],
    "clangd_10": [_clangd_10],
    "clangd_11": [_clangd_11],
    "gopls": [langserver_dir / "bin" / "gopls"],
}


@contextlib.contextmanager
def start_server(langserver_name, project_root, file_contents):
    command = SERVER_COMMANDS[langserver_name]

    # Create files before langserver starts
    for fn, text in file_contents.items():
        path = project_root / fn
        path.write_text(text)

    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    tserver = ThreadedServer(process, project_root.as_uri())

    try:
        yield (tserver, project_root)
    except Exception as e:
        # Prevent freezing tests
        process.kill()
        raise e

    tserver.exit_cleanly()


def check_that_langserver_works(langserver_name, tmp_path):
    if langserver_name == "pyls":
        file_contents = {
            "foo.py": textwrap.dedent(
                f"""\
                import sys
                def do_foo():
                    sys.getdefaultencoding()
                def do_bar():
                    sys.intern("hey")

                do_ #{METHOD_COMPLETION}-1"""
            )
        }
        filename = "foo.py"
        language_id = "python"

    elif langserver_name == "js":
        file_contents = {
            "foo.js": textwrap.dedent(
                f"""\
                function doSomethingWithFoo(x, y) {{
                    const blah = x + y;
                    return asdf asdf;
                }}

                doS //#{METHOD_COMPLETION}-3"""
            )
        }
        filename = "foo.js"
        language_id = "javascript"

    elif langserver_name in ("clangd_10", "clangd_11"):
        file_contents = {
            "foo.c": textwrap.dedent(
                f"""\
                #include <stdio.h>
                void do_foo(void);
                void do_foo(void) {{
                }}
                int do_bar(char x, long y) {{
                    short z = x + y;
                }}

                int main(void) {{ do_ //#{METHOD_COMPLETION}-3"""
            )
        }
        filename = "foo.c"
        language_id = "c"

    elif langserver_name == "gopls":
        file_contents = {
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
                    cat := &Creature{{"cat"}}
                    cat := &Creature{{"cat"}}
                    cat.Dump()
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
        filename = "foo.go"
        language_id = "go"
    else:
        raise ValueError(langserver_name)

    with start_server(langserver_name, tmp_path, file_contents) as (
        tserver,
        project_root,
    ):
        # Initialized #####
        tserver.wait_for_message_of_type(lsp.Initialized)
        tserver.lsp_client.did_open(
            lsp.TextDocumentItem(
                uri=(project_root / filename).as_uri(),
                languageId=language_id,
                text=file_contents[filename],
                version=0,
            )
        )

        # Diagnostics #####
        diagnostics = tserver.wait_for_message_of_type(lsp.PublishDiagnostics)
        assert diagnostics.uri == (project_root / filename).as_uri()
        diag_msgs = [diag.message for diag in diagnostics.diagnostics]

        if langserver_name == "pyls":
            assert "undefined name 'do_'" in diag_msgs
            assert "E302 expected 2 blank lines, found 0" in diag_msgs
            assert "W292 no newline at end of file" in diag_msgs
        elif langserver_name == "js":
            assert diag_msgs == ["';' expected."]
        elif langserver_name in ("clangd_10", "clangd_11"):
            assert diag_msgs == [
                "Non-void function does not return a value",
                "Use of undeclared identifier 'do_'",
                "Expected '}'\n\nfoo.c:9:16: note: to match this '{'",
                "To match this '{'\n\nfoo.c:9:37: error: expected '}'",
            ]
        elif langserver_name == "gopls":
            assert diag_msgs == ["expected ';', found asdf"]
        else:
            raise ValueError(langserver_name)

        do_method = functools.partial(
            tserver.do_method,
            file_contents[filename],
            (project_root / filename).as_uri(),
        )

        completions = do_method(METHOD_COMPLETION)
        completion_labels = [item.label for item in completions.completion_list.items]

        if langserver_name == "pyls":
            assert completion_labels == ["do_bar()", "do_foo()"]
        elif langserver_name in ("js", "gopls"):
            assert "doSomethingWithFoo" in completion_labels
        elif langserver_name in ("clangd_10", "clangd_11"):
            assert " do_foo()" in completion_labels
            assert " do_bar(char x, long y)" in completion_labels
        else:
            raise ValueError(langserver_name)


def _needs_clangd(version):
    return pytest.mark.skipif(
        not list(langserver_dir.glob(f"clangd_{version}.*")),
        reason=f"clangd {version} not found",
    )


def test_pyls(tmp_path):
    check_that_langserver_works("pyls", tmp_path)


@pytest.mark.skipif(
    not (langserver_dir / "node_modules/.bin/javascript-typescript-stdio").exists(),
    reason="javascript-typescript-langserver not found",
)
@pytest.mark.skipif(shutil.which("node") is None, reason="node not found in $PATH")
def test_javascript_typescript_langserver(tmp_path):
    check_that_langserver_works("js", tmp_path)


@pytest.mark.skipif(
    sys.platform == "win32", reason="don't know how clangd works on windows"
)
@pytest.mark.skipif(_clangd_10 is None, reason="clangd 10 not found")
def test_clangd_10(tmp_path):
    check_that_langserver_works("clangd_10", tmp_path)


@pytest.mark.skipif(
    sys.platform == "win32", reason="don't know how clangd works on windows"
)
@pytest.mark.skipif(_clangd_11 is None, reason="clangd 11 not found")
def test_clangd_11(tmp_path):
    check_that_langserver_works("clangd_11", tmp_path)


@pytest.mark.xfail(
    strict=True, reason="gopls needs WorkspaceFolders, not implemented yet"
)
@pytest.mark.skipif(
    sys.platform == "win32", reason="don't know how go works on windows"
)
@pytest.mark.skipif(
    not (langserver_dir / "bin" / "gopls").exists(),
    reason="gopls not installed in tests/langservers/bin/gopls",
)
def test_gopls(tmp_path):
    check_that_langserver_works("gopls", tmp_path)
