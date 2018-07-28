def calculate_change_events(
    old_text: str, new_text: str
) -> t.List[lsp.TextDocumentContentChangeEvent]:
    matcher = difflib.SequenceMatcher(a=old_text, b=new_text)
    events = []

    def index_to_position(index: int, text: str) -> lsp.Position:
        line = text.count("\n", 0, index)
        character = index - (text.rfind("\n", 0, index) + 1)
        return lsp.Position(line=line, character=character)

    for (
        opcode,
        old_start,
        old_end,
        new_start,
        new_end,
    ) in matcher.get_opcodes():
        if opcode == "equal":
            continue

        replacement = new_text[new_start:new_end]

        how_many_deleted = old_end - old_start
        how_many_inserted = new_end - new_start
        end = new_start + how_many_deleted

        start_pos = index_to_position(new_start, new_text)
        end_pos = index_to_position(end, new_text)

        events.append(
            lsp.TextDocumentContentChangeEvent.change_range(
                change_start=start_pos,
                change_end=end_pos,
                change_text=replacement,
                old_text=old_text,
            )
        )
    return events
