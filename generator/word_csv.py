from __future__ import annotations

import csv
from pathlib import Path


def read_word_rows(path: Path) -> list[tuple[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        rows = [
            [cell.strip() for cell in row]
            for row in csv.reader(source)
            if row and any(cell.strip() for cell in row)
        ]

    if not rows:
        return []

    header = [cell.casefold() for cell in rows[0]]
    has_header = "answer" in header or "description" in header or "clue" in header
    if has_header:
        answer_index = header.index("answer") if "answer" in header else 0
        if "description" in header:
            clue_index = header.index("description")
        elif "clue" in header:
            clue_index = header.index("clue")
        else:
            clue_index = 1
        data_rows = rows[1:]
    else:
        answer_index = 0
        clue_index = 1
        data_rows = rows

    parsed = []
    for row in data_rows:
        if len(row) <= answer_index:
            continue
        answer = row[answer_index].strip()
        clue = row[clue_index].strip() if len(row) > clue_index else ""
        if answer and clue:
            parsed.append((answer, clue))
    return parsed
