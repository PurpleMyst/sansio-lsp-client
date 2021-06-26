import sansio_lsp_client as lsp


def test_change_range():
    # "foo\nbar2 --> "fOO\nbar"
    assert lsp.TextDocumentContentChangeEvent.change_range(
        lsp.Position(line=0, character=1),
        lsp.Position(line=0, character=3),
        "OO",
        "foo\nbar",
    ) == lsp.TextDocumentContentChangeEvent(
        range=lsp.Range(
            start=lsp.Position(line=0, character=1),  # f|oo
            end=lsp.Position(line=0, character=3),  # foo|
        ),
        rangeLength=len("oo"),
        text="OO",
    )

    # "foo\nbar\nbaz" --> "foLOLz"
    assert lsp.TextDocumentContentChangeEvent.change_range(
        lsp.Position(line=0, character=2),
        lsp.Position(line=2, character=2),
        "LOL",
        "foo\nbar\nbaz",
    ) == lsp.TextDocumentContentChangeEvent(
        range=lsp.Range(
            start=lsp.Position(line=0, character=2),  # fo|o
            end=lsp.Position(line=2, character=2),  # ba|z
        ),
        rangeLength=len("o" + "bar" + "ba"),  # FIXME: include newlines?
        text="LOL",
    )
