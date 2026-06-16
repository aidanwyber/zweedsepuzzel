from __future__ import annotations

import argparse
import csv
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Direction = Literal["right", "down"]
CellType = Literal["letter", "clue", "block"]

IJ_TOKEN = "Ĳ"


@dataclass(frozen=True)
class WordEntry:
    id: str
    answer: str
    clue: str
    letters: tuple[str, ...]

    @property
    def length(self) -> int:
        return len(self.letters)


@dataclass(frozen=True)
class Slot:
    id: str
    direction: Direction
    origin: tuple[int, int]
    cells: tuple[tuple[int, int], ...]

    @property
    def length(self) -> int:
        return len(self.cells)


@dataclass(frozen=True)
class Template:
    id: str
    title: str
    width: int
    height: int
    slots: tuple[Slot, ...]


@dataclass(frozen=True)
class Overlap:
    a_slot: str
    a_index: int
    b_slot: str
    b_index: int


def tokenize_answer(answer: str) -> tuple[str, ...]:
    normalized = re.sub(r"[^A-ZĲIJ]", "", answer.upper())
    letters: list[str] = []
    i = 0
    while i < len(normalized):
        if normalized[i : i + 2] == "IJ":
            letters.append(IJ_TOKEN)
            i += 2
        else:
            letters.append(normalized[i])
            i += 1
    return tuple(letters)


def display_letter(letter: str) -> str:
    return "IJ" if letter == IJ_TOKEN else letter


def load_words(path: Path) -> list[WordEntry]:
    with path.open(newline="", encoding="utf-8") as source:
        rows = csv.DictReader(source)
        entries = []
        for index, row in enumerate(rows, start=1):
            answer = row["answer"].strip()
            clue = row.get("description", row.get("clue", "")).strip()
            letters = tokenize_answer(answer)
            if answer and clue and letters:
                entries.append(
                    WordEntry(
                        id=f"w{index}",
                        answer=answer.upper(),
                        clue=clue,
                        letters=letters,
                    )
                )
    return entries


def compact_template() -> Template:
    return Template(
        id="compact-6x6",
        title="Compacte Zweedse puzzel",
        width=6,
        height=6,
        slots=(
            Slot("h1", "right", (1, 0), ((1, 1), (1, 2), (1, 3), (1, 4), (1, 5))),
            Slot("h2", "right", (5, 0), ((5, 1), (5, 2), (5, 3), (5, 4), (5, 5))),
            Slot("v1", "down", (0, 1), ((1, 1), (2, 1), (3, 1), (4, 1))),
            Slot("v2", "down", (0, 2), ((1, 2), (2, 2), (3, 2))),
            Slot("v3", "down", (0, 3), ((1, 3), (2, 3), (3, 3), (4, 3), (5, 3))),
            Slot("v4", "down", (0, 4), ((1, 4), (2, 4), (3, 4), (4, 4))),
            Slot("v5", "down", (0, 5), ((1, 5), (2, 5), (3, 5), (4, 5))),
        ),
    )


def offset_slot(slot: Slot, prefix: str, row_offset: int, col_offset: int) -> Slot:
    return Slot(
        id=f"{prefix}_{slot.id}",
        direction=slot.direction,
        origin=(slot.origin[0] + row_offset, slot.origin[1] + col_offset),
        cells=tuple((row + row_offset, col + col_offset) for row, col in slot.cells),
    )


def offset_slots(slots: tuple[Slot, ...], prefix: str, row_offset: int, col_offset: int) -> tuple[Slot, ...]:
    return tuple(offset_slot(slot, prefix, row_offset, col_offset) for slot in slots)


def wide_10x17_template() -> Template:
    compact_slots = compact_template().slots
    top_cluster = offset_slots(compact_slots, "top", 0, 0)
    lower_cluster = offset_slots(compact_slots, "lower", 10, 3)
    return Template(
        id="10x17",
        title="Zweedse puzzel 10x17",
        width=10,
        height=17,
        slots=top_cluster + lower_cluster,
    )


def available_templates() -> dict[str, Template]:
    templates = (compact_template(), wide_10x17_template())
    return {template.id: template for template in templates}


def derive_overlaps(slots: tuple[Slot, ...]) -> list[Overlap]:
    by_cell: dict[tuple[int, int], list[tuple[str, int]]] = {}
    for slot in slots:
        for index, cell in enumerate(slot.cells):
            by_cell.setdefault(cell, []).append((slot.id, index))

    overlaps: list[Overlap] = []
    for occupants in by_cell.values():
        for left_index, left in enumerate(occupants):
            for right in occupants[left_index + 1 :]:
                overlaps.append(Overlap(left[0], left[1], right[0], right[1]))
                overlaps.append(Overlap(right[0], right[1], left[0], left[1]))
    return overlaps


def build_domains(slots: tuple[Slot, ...], words: list[WordEntry]) -> dict[str, list[WordEntry]]:
    by_length: dict[int, list[WordEntry]] = {}
    for word in words:
        by_length.setdefault(word.length, []).append(word)
    return {slot.id: list(by_length.get(slot.length, [])) for slot in slots}


class Solver:
    def __init__(self, template: Template, words: list[WordEntry], seed: int = 7) -> None:
        self.template = template
        self.slots = {slot.id: slot for slot in template.slots}
        self.domains = build_domains(template.slots, words)
        self.overlaps = derive_overlaps(template.slots)
        self.neighbors: dict[str, list[Overlap]] = {slot.id: [] for slot in template.slots}
        for overlap in self.overlaps:
            self.neighbors[overlap.a_slot].append(overlap)
        self.random = random.Random(seed)

    def solve(self) -> dict[str, WordEntry] | None:
        return self._search({})

    def count_solutions(self, limit: int = 2) -> int:
        return self._count({}, limit)

    def _candidate_words(
        self, slot_id: str, assignment: dict[str, WordEntry]
    ) -> list[WordEntry]:
        candidates = []
        used_ids = {word.id for word in assignment.values()}
        for word in self.domains[slot_id]:
            if word.id in used_ids:
                continue
            if self._fits(slot_id, word, assignment):
                candidates.append(word)
        return candidates

    def _fits(
        self, slot_id: str, word: WordEntry, assignment: dict[str, WordEntry]
    ) -> bool:
        for overlap in self.neighbors[slot_id]:
            other = assignment.get(overlap.b_slot)
            if other is None:
                continue
            if word.letters[overlap.a_index] != other.letters[overlap.b_index]:
                return False
        return True

    def _select_slot(self, assignment: dict[str, WordEntry]) -> str:
        open_slot_ids = [slot_id for slot_id in self.slots if slot_id not in assignment]
        scored = []
        for slot_id in open_slot_ids:
            candidates = self._candidate_words(slot_id, assignment)
            degree = len(self.neighbors[slot_id])
            length = self.slots[slot_id].length
            scored.append((len(candidates), -degree, -length, slot_id))
        scored.sort()
        return scored[0][3]

    def _ordered_candidates(
        self, slot_id: str, assignment: dict[str, WordEntry]
    ) -> list[WordEntry]:
        candidates = self._candidate_words(slot_id, assignment)
        self.random.shuffle(candidates)

        def constraining_score(word: WordEntry) -> int:
            test_assignment = {**assignment, slot_id: word}
            remaining = 0
            for other_id in self.slots:
                if other_id not in test_assignment:
                    remaining += len(self._candidate_words(other_id, test_assignment))
            return -remaining

        return sorted(candidates, key=constraining_score)

    def _has_forward_support(self, assignment: dict[str, WordEntry]) -> bool:
        return all(
            self._candidate_words(slot_id, assignment)
            for slot_id in self.slots
            if slot_id not in assignment
        )

    def _search(self, assignment: dict[str, WordEntry]) -> dict[str, WordEntry] | None:
        if len(assignment) == len(self.slots):
            return assignment

        slot_id = self._select_slot(assignment)
        for word in self._ordered_candidates(slot_id, assignment):
            next_assignment = {**assignment, slot_id: word}
            if self._has_forward_support(next_assignment):
                solved = self._search(next_assignment)
                if solved is not None:
                    return solved
            elif len(next_assignment) == len(self.slots):
                return next_assignment
        return None

    def _count(self, assignment: dict[str, WordEntry], limit: int) -> int:
        if len(assignment) == len(self.slots):
            return 1

        total = 0
        slot_id = self._select_slot(assignment)
        for word in self._ordered_candidates(slot_id, assignment):
            next_assignment = {**assignment, slot_id: word}
            if self._has_forward_support(next_assignment) or len(next_assignment) == len(
                self.slots
            ):
                total += self._count(next_assignment, limit - total)
                if total >= limit:
                    break
        return total


def materialize(template: Template, assignment: dict[str, WordEntry], unique: bool) -> dict:
    slots_by_id = {slot.id: slot for slot in template.slots}
    letter_cells: dict[tuple[int, int], tuple[str, list[str]]] = {}
    clue_cells: dict[tuple[int, int], list[dict]] = {}

    for slot_id, word in assignment.items():
        slot = slots_by_id[slot_id]
        clue_cells.setdefault(slot.origin, []).append(
            {"direction": slot.direction, "text": word.clue, "slotId": slot.id}
        )
        for index, cell in enumerate(slot.cells):
            letter_cells.setdefault(cell, (display_letter(word.letters[index]), []))[1].append(
                slot.id
            )

    rows = []
    for row in range(template.height):
        cells = []
        for col in range(template.width):
            coord = (row, col)
            if coord in clue_cells:
                cells.append({"type": "clue", "clues": clue_cells[coord]})
            elif coord in letter_cells:
                letter, slot_ids = letter_cells[coord]
                cells.append({"type": "letter", "solution": letter, "slotIds": slot_ids})
            else:
                cells.append({"type": "block"})
        rows.append(cells)

    interlocked = sum(1 for _, slot_ids in letter_cells.values() if len(slot_ids) > 1)
    total_cells = template.width * template.height
    letter_count = len(letter_cells)
    clue_count = len(clue_cells)

    return {
        "title": template.title,
        "templateId": template.id,
        "algorithm": "template-driven CSP backtracking with MRV, degree tie-breaks, least-constraining values, and forward checking",
        "width": template.width,
        "height": template.height,
        "unique": unique,
        "cells": rows,
        "slots": [
            {
                "id": slot.id,
                "direction": slot.direction,
                "origin": list(slot.origin),
                "cells": [list(cell) for cell in slot.cells],
                "answer": assignment[slot.id].answer,
                "clue": assignment[slot.id].clue,
            }
            for slot in template.slots
        ],
        "metrics": {
            "fillRate": round(letter_count / total_cells, 3),
            "clueCellRatio": round(clue_count / total_cells, 3),
            "interlockRatio": round(interlocked / letter_count, 3),
            "letterCells": letter_count,
            "clueCells": clue_count,
            "slotCount": len(template.slots),
        },
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    templates = available_templates()
    parser = argparse.ArgumentParser(description="Generate a Swedish-style crossword puzzle.")
    parser.add_argument("--words", type=Path, default=Path("generator/data/dutch_words.csv"))
    parser.add_argument("--out", type=Path, default=Path("generated/puzzle.json"))
    parser.add_argument(
        "--frontend-out", type=Path, default=Path("frontend/public/puzzles/puzzle.json")
    )
    parser.add_argument(
        "--template",
        choices=sorted(templates),
        default="10x17",
        help="Puzzle template to generate.",
    )
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    words = load_words(args.words)
    template = templates[args.template]
    solver = Solver(template, words, seed=args.seed)
    assignment = solver.solve()
    if assignment is None:
        raise SystemExit("No puzzle could be generated for the current template and word list.")

    solution_count = solver.count_solutions(limit=2)
    puzzle = materialize(template, assignment, unique=solution_count == 1)
    write_json(args.out, puzzle)
    write_json(args.frontend_out, puzzle)

    print(f"Generated {puzzle['title']} with {len(puzzle['slots'])} slots.")
    print(f"Unique: {puzzle['unique']}")
    print(f"Wrote {args.out} and {args.frontend_out}")


if __name__ == "__main__":
    main()
