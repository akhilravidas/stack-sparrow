"""
Strings
"""
from typing import List, Tuple

MAX_PADDING = 5


def annotated_file_contents(
    content: str, changed_line_ranges: List[Tuple[int, int]], start: int = 1
) -> str:
    """
    Print contents of a file with line numbers and padding.
    """
    lines = content.splitlines()

    def is_changed_line(line_number):
        return any(start <= line_number <= end for start, end in changed_line_ranges)

    return "\n".join(
        f"{('*' if is_changed_line(start + i) else ' ')}{start + i: >{MAX_PADDING}}{' ' + line if line else ''}"
        for i, line in enumerate(lines)
    )
