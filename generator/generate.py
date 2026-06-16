from __future__ import annotations

import argparse
import csv
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from generator.template import Slot, Template, connected_components, derive_overlaps

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
class QualityProfile:
    name: str
    uniqueness: Literal["none", "structural", "clue"]
    require_connected: bool
    min_fill_rate: float
    min_interlock_ratio: float
    min_slot_count: int
    max_short_word_ratio: float
    max_clue_chars: int


@dataclass(frozen=True)
class QualityReport:
    passed: bool
    score: float
    reasons: tuple[str, ...]
    values: dict[str, float | int | bool]


PUBLISHER_PROFILE = QualityProfile(
    name="publisher",
    uniqueness="clue",
    require_connected=True,
    min_fill_rate=0.60,
    min_interlock_ratio=0.25,
    min_slot_count=24,
    max_short_word_ratio=0.12,
    max_clue_chars=22,
)

DRAFT_PROFILE = QualityProfile(
    name="draft",
    uniqueness="none",
    require_connected=False,
    min_fill_rate=0.0,
    min_interlock_ratio=0.0,
    min_slot_count=1,
    max_short_word_ratio=1.0,
    max_clue_chars=80,
)


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


def dense_10x17_template() -> Template:
    return Template(
        id="10x17",
        title="Zweedse puzzel 10x17",
        width=10,
        height=17,
        slots=(
            Slot("v_landschap", "down", (1, 1), ((2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1), (8, 1), (9, 1), (10, 1))),
            Slot("h_potlood", "right", (10, 0), ((10, 1), (10, 2), (10, 3), (10, 4), (10, 5), (10, 6), (10, 7))),
            Slot("v_computer", "down", (4, 3), ((5, 3), (6, 3), (7, 3), (8, 3), (9, 3), (10, 3), (11, 3), (12, 3))),
            Slot("v_telefoon", "down", (3, 5), ((4, 5), (5, 5), (6, 5), (7, 5), (8, 5), (9, 5), (10, 5), (11, 5))),
            Slot("h_treinstel", "right", (11, 0), ((11, 1), (11, 2), (11, 3), (11, 4), (11, 5), (11, 6), (11, 7), (11, 8), (11, 9))),
            Slot("v_olifant", "down", (8, 4), ((9, 4), (10, 4), (11, 4), (12, 4), (13, 4), (14, 4), (15, 4))),
            Slot("v_dorp", "down", (8, 2), ((9, 2), (10, 2), (11, 2), (12, 2))),
            Slot("v_venster", "down", (9, 8), ((10, 8), (11, 8), (12, 8), (13, 8), (14, 8), (15, 8), (16, 8))),
            Slot("v_schilder", "down", (6, 9), ((7, 9), (8, 9), (9, 9), (10, 9), (11, 9), (12, 9), (13, 9), (14, 9))),
            Slot("v_brood", "down", (5, 7), ((6, 7), (7, 7), (8, 7), (9, 7), (10, 7))),
            Slot("h_winkel", "right", (14, 1), ((14, 2), (14, 3), (14, 4), (14, 5), (14, 6), (14, 7))),
            Slot("h_stoel", "right", (6, 0), ((6, 1), (6, 2), (6, 3), (6, 4), (6, 5))),
            Slot("h_camera", "right", (16, 3), ((16, 4), (16, 5), (16, 6), (16, 7), (16, 8), (16, 9))),
            Slot("h_fietser", "right", (15, 0), ((15, 1), (15, 2), (15, 3), (15, 4), (15, 5), (15, 6), (15, 7))),
            Slot("v_spiegel", "down", (0, 4), ((1, 4), (2, 4), (3, 4), (4, 4), (5, 4), (6, 4), (7, 4))),
            Slot("h_alarm", "right", (13, 1), ((13, 2), (13, 3), (13, 4), (13, 5), (13, 6))),
            Slot("v_fluit", "down", (1, 2), ((2, 2), (3, 2), (4, 2), (5, 2), (6, 2))),
            Slot("v_roos", "down", (7, 6), ((8, 6), (9, 6), (10, 6), (11, 6))),
            Slot("h_school", "right", (1, 3), ((1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9))),
            Slot("v_oven", "down", (0, 7), ((1, 7), (2, 7), (3, 7), (4, 7))),
            Slot("v_huis", "down", (0, 6), ((1, 6), (2, 6), (3, 6), (4, 6))),
            Slot("v_lepel", "down", (0, 9), ((1, 9), (2, 9), (3, 9), (4, 9), (5, 9))),
            Slot("v_oever", "down", (0, 8), ((1, 8), (2, 8), (3, 8), (4, 8), (5, 8))),
            Slot("h_wind", "right", (12, 5), ((12, 6), (12, 7), (12, 8), (12, 9))),
        ),
    )


def available_templates() -> dict[str, Template]:
    templates = (compact_template(), dense_10x17_template())
    available = {template.id: template for template in templates}
    available.update(Template.load_many(Path("generator/templates")))
    return available


def available_profiles() -> dict[str, QualityProfile]:
    profiles = (PUBLISHER_PROFILE, DRAFT_PROFILE)
    return {profile.name: profile for profile in profiles}


def build_domains(slots: tuple[Slot, ...], words: list[WordEntry]) -> dict[str, list[WordEntry]]:
    by_length: dict[int, list[WordEntry]] = {}
    for word in words:
        by_length.setdefault(word.length, []).append(word)
    return {slot.id: list(by_length.get(slot.length, [])) for slot in slots}


def normalize_clue(clue: str) -> str:
    return re.sub(r"\s+", " ", clue.strip().casefold())


def clue_unique(slots: list[dict], words: list[WordEntry]) -> bool:
    clue_to_answers: dict[str, set[str]] = {}
    for word in words:
        clue_to_answers.setdefault(normalize_clue(word.clue), set()).add(word.answer)

    selected_clues = [normalize_clue(slot["clue"]) for slot in slots]
    if len(selected_clues) != len(set(selected_clues)):
        return False

    return all(len(clue_to_answers.get(clue, set())) == 1 for clue in selected_clues)


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


def evaluate_quality(
    template: Template, puzzle: dict, profile: QualityProfile, words: list[WordEntry]
) -> QualityReport:
    metrics = puzzle["metrics"]
    slots = puzzle["slots"]
    overlaps = derive_overlaps(template.slots)
    components = connected_components(template.slots, overlaps)
    unterminated_slots = template.unterminated_slots()
    short_words = sum(1 for slot in slots if len(tokenize_answer(slot["answer"])) <= 3)
    short_word_ratio = short_words / len(slots) if slots else 1.0
    longest_clue = max((len(slot["clue"]) for slot in slots), default=0)
    clues_unique = clue_unique(slots, words)

    values: dict[str, float | int | bool] = {
        "structuralUnique": puzzle["unique"],
        "clueUnique": clues_unique,
        "fillRate": metrics["fillRate"],
        "interlockRatio": metrics["interlockRatio"],
        "slotCount": metrics["slotCount"],
        "shortWordRatio": round(short_word_ratio, 3),
        "longestClue": longest_clue,
        "components": components,
        "unterminatedSlotCount": len(unterminated_slots),
    }

    reasons: list[str] = []
    if profile.uniqueness == "structural" and not puzzle["unique"]:
        reasons.append("fill is not structurally unique")
    if profile.uniqueness == "clue" and not clues_unique:
        reasons.append("slot clues are not unique within the CSV")
    if profile.require_connected and components != 1:
        reasons.append(f"slot graph has {components} disconnected components")
    if metrics["fillRate"] < profile.min_fill_rate:
        reasons.append(
            f"fill rate {metrics['fillRate']:.3f} is below {profile.min_fill_rate:.3f}"
        )
    if metrics["interlockRatio"] < profile.min_interlock_ratio:
        reasons.append(
            "interlock ratio "
            f"{metrics['interlockRatio']:.3f} is below {profile.min_interlock_ratio:.3f}"
        )
    if metrics["slotCount"] < profile.min_slot_count:
        reasons.append(f"slot count {metrics['slotCount']} is below {profile.min_slot_count}")
    if short_word_ratio > profile.max_short_word_ratio:
        reasons.append(
            f"short-word ratio {short_word_ratio:.3f} is above {profile.max_short_word_ratio:.3f}"
        )
    if longest_clue > profile.max_clue_chars:
        reasons.append(f"longest clue has {longest_clue} chars, above {profile.max_clue_chars}")

    score = (
        metrics["fillRate"] * 35
        + metrics["interlockRatio"] * 35
        + min(metrics["slotCount"] / max(profile.min_slot_count, 1), 1.0) * 15
        + (1.0 - min(short_word_ratio, 1.0)) * 10
        + (5 if puzzle["unique"] else 0)
    )
    if components > 1:
        score -= (components - 1) * 10

    return QualityReport(
        passed=not reasons,
        score=round(score, 3),
        reasons=tuple(reasons),
        values=values,
    )


def attach_quality(puzzle: dict, report: QualityReport, profile: QualityProfile) -> dict:
    puzzle["quality"] = {
        "profile": profile.name,
        "passed": report.passed,
        "score": report.score,
        "reasons": list(report.reasons),
        "values": report.values,
    }
    return puzzle


def generate_best_candidate(
    template: Template,
    words: list[WordEntry],
    profile: QualityProfile,
    attempts: int,
    seed: int,
) -> tuple[dict | None, QualityReport | None, dict | None, QualityReport | None]:
    best_puzzle: dict | None = None
    best_report: QualityReport | None = None
    best_passing_puzzle: dict | None = None
    best_passing_report: QualityReport | None = None

    for attempt in range(attempts):
        attempt_seed = seed + attempt
        solver = Solver(template, words, seed=attempt_seed)
        assignment = solver.solve()
        if assignment is None:
            continue

        solution_count = solver.count_solutions(limit=2)
        puzzle = materialize(template, assignment, unique=solution_count == 1)
        puzzle["generation"] = {"attempt": attempt + 1, "attempts": attempts, "seed": attempt_seed}
        report = evaluate_quality(template, puzzle, profile, words)
        attach_quality(puzzle, report, profile)

        if best_report is None or report.score > best_report.score:
            best_puzzle = puzzle
            best_report = report

        if report.passed and (
            best_passing_report is None or report.score > best_passing_report.score
        ):
            best_passing_puzzle = puzzle
            best_passing_report = report

    return best_passing_puzzle, best_passing_report, best_puzzle, best_report


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    templates = available_templates()
    profiles = available_profiles()
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
    parser.add_argument(
        "--quality",
        choices=sorted(profiles),
        default="publisher",
        help="Quality profile to enforce before writing output.",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=200,
        help="Number of candidate fills to try before choosing the best passing puzzle.",
    )
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    words = load_words(args.words)
    template = templates[args.template]
    profile = profiles[args.quality]
    passing_puzzle, passing_report, best_puzzle, best_report = generate_best_candidate(
        template=template,
        words=words,
        profile=profile,
        attempts=max(args.attempts, 1),
        seed=args.seed,
    )

    if profile.name == "publisher" and passing_puzzle is None:
        if best_report is None:
            raise SystemExit("No puzzle could be generated for the current template and word list.")
        reason_lines = "\n".join(f"- {reason}" for reason in best_report.reasons)
        raise SystemExit(
            "No publisher-grade puzzle found. Best rejected candidate:\n"
            f"score: {best_report.score}\n"
            f"{reason_lines}"
        )

    puzzle = passing_puzzle if passing_puzzle is not None else best_puzzle
    report = passing_report if passing_report is not None else best_report
    if puzzle is None or report is None:
        raise SystemExit("No puzzle could be generated for the current template and word list.")

    write_json(args.out, puzzle)
    write_json(args.frontend_out, puzzle)

    print(f"Generated {puzzle['title']} with {len(puzzle['slots'])} slots.")
    print(f"Quality: {profile.name}, passed: {report.passed}, score: {report.score}")
    print(f"Structural unique: {puzzle['unique']}")
    print(f"Wrote {args.out} and {args.frontend_out}")


if __name__ == "__main__":
    main()
