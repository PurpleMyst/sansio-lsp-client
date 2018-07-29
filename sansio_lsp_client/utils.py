import typing as t
import difflib

from .structs import TextDocumentContentChangeEvent, Position

# Thanks to Akuli for writing most of this code!
# XXX: This code has been through many iterations and even now I'm not sure
# it's correct. It's pretty hard code to test, but I'll eventually get around
# to it.
def calculate_change_events(
    old_text: str, new_text: str
) -> t.List[TextDocumentContentChangeEvent]:
    seq_matcher = difflib.SequenceMatcher(a=old_text, b=new_text)
    events = []

    adjusted_text = old_text[:]

    index_offset = 0

    def index_to_position(index: int) -> Position:
        line = adjusted_text.count("\n", 0, index)
        character = index - (adjusted_text.rfind("\n", 0, index) + 1)
        return Position(line=line, character=character)

    for (
        opcode,
        old_start,
        old_end,
        new_start,
        new_end,
    ) in seq_matcher.get_opcodes():
        if opcode == "equal":
            continue

        adjusted_start_index = old_start + index_offset
        adjusted_end_index = old_end + index_offset

        # To tell how many characters we're about to insert, we just need to
        # know the length of the replacement text. However, we may be replacing
        # some characters that are already there, so we just need to subtract
        # the length of the replacement bit. This will be equal to 0 if we're
        # inserting new text.
        index_offset += len(new_text[new_start:new_end]) - (
            adjusted_end_index - adjusted_start_index
        )

        adjusted_start_pos = index_to_position(adjusted_start_index)
        adjusted_end_pos = index_to_position(adjusted_end_index)

        events.append(
            TextDocumentContentChangeEvent.change_range(
                change_start=adjusted_start_pos,
                change_end=adjusted_end_pos,
                change_text=new_text[new_start:new_end],
                old_text=adjusted_text,
            )
        )

        # Now we'll make the adjusted text actually reflect the changes.
        adjusted_text = (
            adjusted_text[:adjusted_start_index]
            + new_text[new_start:new_end]
            + adjusted_text[adjusted_end_index:]
        )
    return events
