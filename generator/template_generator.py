from __future__ import annotations

import argparse
import csv
import random
import re
from dataclasses import dataclass
from pathlib import Path

from generator.config import config_value, load_config
from generator.generate import DRAFT_PROFILE, generate_best_candidate, load_words, write_json
from generator.template import Direction, Slot, Template


@dataclass(frozen=True)
class WordShape:
    answer: str
    letters: tuple[str, ...]

    @property
    def length(self) -> int:
        return len(self.letters)


@dataclass(frozen=True)
class Placement:
    word: WordShape
    direction: Direction
    clue_direction: Direction
    origin: tuple[int, int]
    cells: tuple[tuple[int, int], ...]

    def stop_cell(self) -> tuple[int, int]:
        row, col = self.cells[-1]
        if self.direction == "right":
            return row, col + 1
        return row + 1, col


@dataclass(frozen=True)
class TemplateEvaluation:
    score: float
    passed: bool
    reasons: tuple[str, ...]
    metrics: dict[str, float | int | bool]


@dataclass(frozen=True)
class TemplateQualitySettings:
    min_fill_rate: float = 0.56
    min_interlock_ratio: float = 0.19
    min_slot_count: int = 21
    max_short_slot_ratio: float = 0.12
    max_clue_cell_ratio: float = 0.30
    min_clue_cell_ratio: float = 0.12
    target_slot_count: int = 30
    dual_clue_bonus_cap: int = 8

    @classmethod
    def from_config(cls, config: dict) -> TemplateQualitySettings:
        return cls(
            min_fill_rate=float(config_value(config, "minFillRate", cls.min_fill_rate)),
            min_interlock_ratio=float(
                config_value(config, "minInterlockRatio", cls.min_interlock_ratio)
            ),
            min_slot_count=int(config_value(config, "minSlotCount", cls.min_slot_count)),
            max_short_slot_ratio=float(
                config_value(config, "maxShortSlotRatio", cls.max_short_slot_ratio)
            ),
            max_clue_cell_ratio=float(
                config_value(config, "maxClueCellRatio", cls.max_clue_cell_ratio)
            ),
            min_clue_cell_ratio=float(
                config_value(config, "minClueCellRatio", cls.min_clue_cell_ratio)
            ),
            target_slot_count=int(
                config_value(config, "targetSlotCount", cls.target_slot_count)
            ),
            dual_clue_bonus_cap=int(
                config_value(config, "dualClueBonusCap", cls.dual_clue_bonus_cap)
            ),
        )


@dataclass(frozen=True)
class SearchResults:
    passing: tuple[tuple[TemplateEvaluation, Template], ...]
    rejected: tuple[tuple[TemplateEvaluation, Template], ...]
    puzzles: dict[str, dict]
    attempted: int


def tokenize(answer: str) -> tuple[str, ...]:
    normalized = re.sub(r"[^A-ZĲIJ]", "", answer.upper())
    letters: list[str] = []
    index = 0
    while index < len(normalized):
        if normalized[index : index + 2] == "IJ":
            letters.append("Ĳ")
            index += 2
        else:
            letters.append(normalized[index])
            index += 1
    return tuple(letters)


def display_answer(letters: tuple[str, ...]) -> str:
    return "".join("IJ" if letter == "Ĳ" else letter for letter in letters)


def load_word_shapes(path: Path, max_length: int) -> list[WordShape]:
    seen: set[str] = set()
    words: list[WordShape] = []
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            answer = row["answer"].strip().upper()
            letters = tokenize(answer)
            if 3 <= len(letters) <= max_length and answer not in seen:
                seen.add(answer)
                words.append(WordShape(answer=answer, letters=letters))
    return words


def all_placements(words: list[WordShape], width: int, height: int) -> list[Placement]:
    placements: list[Placement] = []
    for word in words:
        for row in range(height):
            for col in range(1, width - word.length + 1):
                cells = tuple((row, col + index) for index in range(word.length))
                placements.append(
                    Placement(
                        word=word,
                        direction="right",
                        clue_direction="right",
                        origin=(row, col - 1),
                        cells=cells,
                    )
                )
            for col in range(0, width - word.length + 1):
                if row == 0:
                    continue
                cells = tuple((row, col + index) for index in range(word.length))
                placements.append(
                    Placement(
                        word=word,
                        direction="right",
                        clue_direction="down",
                        origin=(row - 1, col),
                        cells=cells,
                    )
                )

        for row in range(1, height - word.length + 1):
            for col in range(width):
                cells = tuple((row + index, col) for index in range(word.length))
                placements.append(
                    Placement(
                        word=word,
                        direction="down",
                        clue_direction="down",
                        origin=(row - 1, col),
                        cells=cells,
                    )
                )
        for row in range(0, height - word.length + 1):
            for col in range(1, width):
                cells = tuple((row + index, col) for index in range(word.length))
                placements.append(
                    Placement(
                        word=word,
                        direction="down",
                        clue_direction="right",
                        origin=(row, col - 1),
                        cells=cells,
                    )
                )
    return placements


def filter_placements_by_direction(
    placements: list[Placement], allowed_directions: set[Direction]
) -> list[Placement]:
    return [
        placement
        for placement in placements
        if placement.clue_direction in allowed_directions
    ]


def placement_index(placements: list[Placement]) -> dict[tuple[tuple[int, int], str], list[Placement]]:
    indexed: dict[tuple[tuple[int, int], str], list[Placement]] = {}
    for placement in placements:
        for cell, letter in zip(placement.cells, placement.word.letters):
            indexed.setdefault((cell, letter), []).append(placement)
    return indexed


def cross_entry_block_cells(
    placement: Placement, width: int, height: int
) -> set[tuple[int, int]]:
    if placement.direction == placement.clue_direction or not placement.cells:
        return set()

    first_cell = placement.cells[0]
    allowed = {placement.origin}
    if len(placement.cells) > 1:
        allowed.add(placement.cells[1])

    row, col = first_cell
    blocked = set()
    for cell in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
        cell_row, cell_col = cell
        if cell in allowed:
            continue
        if 0 <= cell_row < height and 0 <= cell_col < width:
            blocked.add(cell)
    return blocked


def can_place(
    board: dict[tuple[int, int], str],
    clue_directions: dict[tuple[int, int], set[Direction]],
    reserved_stops: set[tuple[int, int]],
    reserved_blocks: set[tuple[int, int]],
    used_words: set[str],
    slots: list[Placement],
    placement: Placement,
    width: int,
    height: int,
    max_clues_per_cell: int,
) -> bool:
    if placement.word.answer in used_words:
        return False
    if placement.origin in board:
        return False
    existing_clue_directions = clue_directions.get(placement.origin, set())
    if len(existing_clue_directions) >= max_clues_per_cell:
        return False
    if placement.clue_direction in existing_clue_directions:
        return False

    placement_cells = set(placement.cells)
    for existing in slots:
        if existing.direction == placement.direction and placement_cells.intersection(
            existing.cells
        ):
            return False

    for cell, letter in zip(placement.cells, placement.word.letters):
        if cell in reserved_stops or cell in reserved_blocks:
            return False
        if cell in clue_directions:
            return False
        current = board.get(cell)
        if current is not None and current != letter:
            return False

    for cell in cross_entry_block_cells(placement, width, height):
        if cell in board:
            return False

    stop_cell = placement.stop_cell()
    row, col = stop_cell
    if 0 <= row < height and 0 <= col < width and stop_cell in board:
        return False
    return True


def place(
    board: dict[tuple[int, int], str],
    clue_directions: dict[tuple[int, int], set[Direction]],
    reserved_stops: set[tuple[int, int]],
    reserved_blocks: set[tuple[int, int]],
    used_words: set[str],
    slots: list[Placement],
    placement: Placement,
    width: int,
    height: int,
) -> tuple[
    dict[tuple[int, int], str],
    dict[tuple[int, int], set[Direction]],
    set[tuple[int, int]],
    set[tuple[int, int]],
    set[str],
    list[Placement],
]:
    next_board = board.copy()
    next_clues = {cell: set(directions) for cell, directions in clue_directions.items()}
    next_reserved = set(reserved_stops)
    next_reserved_blocks = set(reserved_blocks)
    next_used = set(used_words)
    next_slots = slots[:]

    next_clues.setdefault(placement.origin, set()).add(placement.clue_direction)
    for cell, letter in zip(placement.cells, placement.word.letters):
        next_board[cell] = letter
    stop_cell = placement.stop_cell()
    row, col = stop_cell
    if 0 <= row < height and 0 <= col < width:
        next_reserved.add(stop_cell)
    next_reserved_blocks.update(cross_entry_block_cells(placement, width, height))
    next_used.add(placement.word.answer)
    next_slots.append(placement)
    return next_board, next_clues, next_reserved, next_reserved_blocks, next_used, next_slots


def candidate_placements(
    board: dict[tuple[int, int], str],
    placements: list[Placement],
    indexed: dict[tuple[tuple[int, int], str], list[Placement]],
) -> list[Placement]:
    if not board:
        return placements

    candidates: list[Placement] = []
    seen: set[int] = set()
    for cell, letter in board.items():
        for placement in indexed.get((cell, letter), []):
            identity = id(placement)
            if identity not in seen:
                seen.add(identity)
                candidates.append(placement)
    return candidates


def slots_to_template(
    slots: list[Placement], width: int, height: int, template_id: str, title: str
) -> Template:
    template_slots = []
    for index, placement in enumerate(slots, start=1):
        prefix = "h" if placement.direction == "right" else "v"
        template_slots.append(
            Slot(
                id=f"{prefix}_{index:03d}_len{placement.word.length}",
                direction=placement.direction,
                origin=placement.origin,
                cells=placement.cells,
                clue_direction=placement.clue_direction,
            )
        )
    return Template(
        id=template_id,
        title=title,
        width=width,
        height=height,
        slots=tuple(template_slots),
    )


def run_origin(
    direction: Direction,
    cells: tuple[tuple[int, int], ...],
    clue_direction: Direction | None = None,
) -> tuple[int, int]:
    arrow = clue_direction or direction
    row, col = cells[0]
    if arrow == "right":
        return row, col - 1
    return row - 1, col


def can_add_promoted_slot(
    template: Template,
    direction: Direction,
    clue_direction: Direction,
    cells: tuple[tuple[int, int], ...],
    max_clues_per_cell: int,
) -> bool:
    origin = run_origin(direction, cells, clue_direction)
    row, col = origin
    if row < 0 or row >= template.height or col < 0 or col >= template.width:
        return False
    if origin in template.letter_cells():
        return False

    clue_directions = template.clue_cell_directions()
    existing_directions = clue_directions.get(origin, set())
    if clue_direction in existing_directions:
        return False
    if len(existing_directions) >= max_clues_per_cell:
        return False

    # A promoted slot may cross perpendicular slots, but it must not duplicate
    # or partially overlap another slot in the same reading direction.
    cell_set = set(cells)
    return not any(
        slot.direction == direction and cell_set.intersection(slot.cells)
        for slot in template.slots
    )


def promoted_slot_options(
    template: Template,
    direction: Direction,
    cells: tuple[tuple[int, int], ...],
    max_clues_per_cell: int,
) -> list[Direction]:
    options: list[Direction] = [direction]
    cross_direction: Direction = "down" if direction == "right" else "right"
    options.append(cross_direction)

    valid = []
    for clue_direction in options:
        if not can_add_promoted_slot(
            template, direction, clue_direction, cells, max_clues_per_cell
        ):
            continue

        candidate = Slot(
            id="_entry_check",
            direction=direction,
            origin=run_origin(direction, cells, clue_direction),
            cells=cells,
            clue_direction=clue_direction,
        )
        probe = Template(
            id=template.id,
            title=template.title,
            width=template.width,
            height=template.height,
            slots=tuple((*template.slots, candidate)),
        )
        if not probe.invalid_cross_entry_cells():
            valid.append(clue_direction)

    clue_cells = template.clue_cells()
    return sorted(
        valid,
        key=lambda clue_direction: (
            run_origin(direction, cells, clue_direction) not in clue_cells,
            clue_direction != direction,
        ),
    )


def readable_answer(
    board: dict[tuple[int, int], str], cells: tuple[tuple[int, int], ...]
) -> str:
    return display_answer(tuple(board[cell] for cell in cells))


def promote_readable_runs(
    template: Template,
    max_clues_per_cell: int,
    board: dict[tuple[int, int], str] | None = None,
    allowed_answers: set[str] | None = None,
    used_answers: set[str] | None = None,
) -> Template:
    current = template
    current_used_answers = set(used_answers or set())
    for _ in range(template.width * template.height):
        unclued_runs = current.unclued_readable_runs()
        if not unclued_runs:
            return current
        promoted: tuple[Direction, Direction, tuple[tuple[int, int], ...], str | None] | None = None
        for direction, cells in unclued_runs:
            clue_options = promoted_slot_options(
                current, direction, cells, max_clues_per_cell
            )
            if not clue_options:
                continue
            answer = None
            if board is not None and allowed_answers is not None:
                answer = readable_answer(board, cells)
                if answer not in allowed_answers or answer in current_used_answers:
                    continue
            promoted = (direction, clue_options[0], cells, answer)
            break

        if promoted is None:
            return current

        direction, clue_direction, cells, answer = promoted
        if answer is not None:
            current_used_answers.add(answer)
        slots = list(current.slots)
        prefix = "h" if direction == "right" else "v"
        first_row, first_col = cells[0]
        slots.append(
            Slot(
                id=f"auto_{prefix}_{first_row:02d}_{first_col:02d}_len{len(cells)}",
                direction=direction,
                origin=run_origin(direction, cells, clue_direction),
                cells=cells,
                clue_direction=clue_direction,
            )
        )
        current = Template(
            id=current.id,
            title=current.title,
            width=current.width,
            height=current.height,
            slots=tuple(slots),
        )

    return current


def evaluate_template(
    template: Template,
    words: list[WordShape],
    max_clues_per_cell: int = 2,
    quality: TemplateQualitySettings = TemplateQualitySettings(),
) -> TemplateEvaluation:
    total_cells = template.width * template.height
    letter_cells: dict[tuple[int, int], int] = {}
    clue_cells: dict[tuple[int, int], int] = {}
    length_counts: dict[int, int] = {}
    for word in words:
        length_counts[word.length] = length_counts.get(word.length, 0) + 1

    uncovered_lengths: set[int] = set()
    short_slots = 0
    for slot in template.slots:
        if slot.length <= 3:
            short_slots += 1
        if length_counts.get(slot.length, 0) == 0:
            uncovered_lengths.add(slot.length)
        clue_cells[slot.origin] = clue_cells.get(slot.origin, 0) + 1
        for cell in slot.cells:
            letter_cells[cell] = letter_cells.get(cell, 0) + 1

    fill_rate = len(letter_cells) / total_cells if total_cells else 0.0
    clue_cell_ratio = len(clue_cells) / total_cells if total_cells else 0.0
    interlock_ratio = (
        sum(1 for count in letter_cells.values() if count > 1) / len(letter_cells)
        if letter_cells
        else 0.0
    )
    slot_count = len(template.slots)
    components = template.connected_components()
    short_slot_ratio = short_slots / slot_count if slot_count else 1.0
    dual_clue_cells = sum(1 for count in clue_cells.values() if count > 1)
    unterminated_slots = template.unterminated_slots()
    invalid_clue_cells = template.invalid_clue_cells(max_clues_per_cell=max_clues_per_cell)
    invalid_cross_entry_cells = template.invalid_cross_entry_cells()
    unclued_runs = template.unclued_readable_runs()

    reasons: list[str] = []
    if invalid_clue_cells:
        reasons.append("; ".join(invalid_clue_cells[:3]))
    if invalid_cross_entry_cells:
        reasons.append("; ".join(invalid_cross_entry_cells[:3]))
    if unclued_runs:
        examples = ", ".join(
            f"{direction}@{cells[0]}" for direction, cells in unclued_runs[:3]
        )
        reasons.append(f"{len(unclued_runs)} unclued readable runs ({examples})")
    if unterminated_slots:
        examples = ", ".join(
            f"{slot_id}@{cell}" for slot_id, cell in unterminated_slots[:3]
        )
        reasons.append(f"{len(unterminated_slots)} unterminated slots ({examples})")
    if components != 1:
        reasons.append(f"slot graph has {components} components")
    if fill_rate < quality.min_fill_rate:
        reasons.append(f"fill rate {fill_rate:.3f} below {quality.min_fill_rate:.3f}")
    if interlock_ratio < quality.min_interlock_ratio:
        reasons.append(
            f"interlock ratio {interlock_ratio:.3f} below {quality.min_interlock_ratio:.3f}"
        )
    if slot_count < quality.min_slot_count:
        reasons.append(f"slot count {slot_count} below {quality.min_slot_count}")
    if short_slot_ratio > quality.max_short_slot_ratio:
        reasons.append(
            f"short slot ratio {short_slot_ratio:.3f} above {quality.max_short_slot_ratio:.3f}"
        )
    if clue_cell_ratio > quality.max_clue_cell_ratio:
        reasons.append(
            f"clue cell ratio {clue_cell_ratio:.3f} above {quality.max_clue_cell_ratio:.3f}"
        )
    if uncovered_lengths:
        reasons.append(f"uncovered slot lengths: {sorted(uncovered_lengths)}")

    # Scoring follows the research report's template-first recommendation:
    # reward high fill, strong interlock, connectedness, enough slots, compact
    # clue-cell use, and word-length coverage before attempting CSP filling.
    score = (
        fill_rate * 35
        + interlock_ratio * 35
        + min(slot_count / max(quality.target_slot_count, 1), 1.0) * 15
        + max(0.0, 1.0 - short_slot_ratio) * 5
        + min(dual_clue_cells / max(quality.dual_clue_bonus_cap, 1), 1.0) * 5
        + (5 if components == 1 else -10 * max(components - 1, 1))
    )
    if clue_cell_ratio < quality.min_clue_cell_ratio:
        score -= (quality.min_clue_cell_ratio - clue_cell_ratio) * 20
    if clue_cell_ratio > quality.max_clue_cell_ratio:
        score -= (clue_cell_ratio - quality.max_clue_cell_ratio) * 20
    score -= len(uncovered_lengths) * 5

    return TemplateEvaluation(
        score=round(score, 3),
        passed=not reasons,
        reasons=tuple(reasons),
        metrics={
            "fillRate": round(fill_rate, 3),
            "clueCellRatio": round(clue_cell_ratio, 3),
            "interlockRatio": round(interlock_ratio, 3),
            "slotCount": slot_count,
            "components": components,
            "shortSlotRatio": round(short_slot_ratio, 3),
            "dualClueCells": dual_clue_cells,
            "uncoveredLengthCount": len(uncovered_lengths),
            "unterminatedSlotCount": len(unterminated_slots),
            "invalidClueCellCount": len(invalid_clue_cells),
            "invalidCrossEntryCellCount": len(invalid_cross_entry_cells),
            "uncluedReadableRunCount": len(unclued_runs),
        },
    )


def reject_with_reason(
    evaluation: TemplateEvaluation, reason: str, metric_key: str
) -> TemplateEvaluation:
    metrics = dict(evaluation.metrics)
    metrics[metric_key] = False
    return TemplateEvaluation(
        score=evaluation.score,
        passed=False,
        reasons=(*evaluation.reasons, reason),
        metrics=metrics,
    )


def search_templates(
    words: list[WordShape],
    fill_words: list,
    width: int,
    height: int,
    attempts: int,
    seed: int,
    keep: int,
    allowed_directions: set[Direction],
    max_clues_per_cell: int,
    quality: TemplateQualitySettings,
    stop_when_enough_passing: bool,
    require_fill: bool,
    fill_attempts: int,
    fill_seed: int,
    verbose: bool = False,
) -> SearchResults:
    placements = filter_placements_by_direction(
        all_placements(words, width, height), allowed_directions
    )
    allowed_answers = {word.answer for word in words}
    indexed = placement_index(placements)
    passing: list[tuple[TemplateEvaluation, Template]] = []
    rejected: list[tuple[TemplateEvaluation, Template]] = []
    puzzles: dict[str, dict] = {}
    attempted = 0

    for attempt in range(attempts):
        attempted += 1
        attempt_seed = seed + attempt
        randomizer = random.Random(attempt_seed)
        board: dict[tuple[int, int], str] = {}
        clues: dict[tuple[int, int], set[Direction]] = {}
        reserved_stops: set[tuple[int, int]] = set()
        reserved_blocks: set[tuple[int, int]] = set()
        used: set[str] = set()
        slots: list[Placement] = []

        for _ in range(90):
            ranked = []
            for placement in candidate_placements(board, placements, indexed):
                if not can_place(
                    board,
                    clues,
                    reserved_stops,
                    reserved_blocks,
                    used,
                    slots,
                    placement,
                    width,
                    height,
                    max_clues_per_cell,
                ):
                    continue
                intersections = sum(1 for cell in placement.cells if cell in board)
                if slots and intersections == 0:
                    continue
                new_cells = sum(1 for cell in placement.cells if cell not in board)
                dual_clue_bonus = 1 if placement.origin in clues else 0
                weight = intersections * 22 + new_cells * 1.2 + placement.word.length * 0.1
                weight += dual_clue_bonus * 3
                ranked.append((weight, placement))

            if not ranked:
                break

            ranked.sort(key=lambda item: item[0], reverse=True)
            pool = ranked[: min(60, len(ranked))]
            placement = randomizer.choice(pool)[1]
            board, clues, reserved_stops, reserved_blocks, used, slots = place(
                board,
                clues,
                reserved_stops,
                reserved_blocks,
                used,
                slots,
                placement,
                width,
                height,
            )

        template = slots_to_template(
            slots=slots,
            width=width,
            height=height,
            template_id=f"random-{width}x{height}-{attempt_seed}",
            title=f"Randomized {width}x{height} template {attempt_seed}",
        )
        template = promote_readable_runs(
            template,
            max_clues_per_cell=max_clues_per_cell,
            board=board,
            allowed_answers=allowed_answers,
            used_answers=used,
        )
        evaluation = evaluate_template(
            template,
            words,
            max_clues_per_cell=max_clues_per_cell,
            quality=quality,
        )

        puzzle = None
        if evaluation.passed and require_fill:
            puzzle, report, _, _ = generate_best_candidate(
                template=template,
                words=fill_words,
                profile=DRAFT_PROFILE,
                attempts=max(fill_attempts, 1),
                seed=fill_seed + attempt,
            )
            if puzzle is None or report is None or not report.passed:
                evaluation = reject_with_reason(
                    evaluation,
                    "no valid fill found",
                    "fillable",
                )

        target = passing if evaluation.passed else rejected
        target.append((evaluation, template))
        target.sort(key=lambda item: item[0].score, reverse=True)
        del target[keep:]
        if evaluation.passed and puzzle is not None:
            puzzles[template.id] = puzzle

        if verbose and evaluation.passed:
            print(
                f"attempt {attempt + 1}/{attempts} seed {attempt_seed}: "
                f"pass, score {evaluation.score}, passes all gates"
            )

        if stop_when_enough_passing and len(passing) >= keep:
            break

    return SearchResults(
        passing=tuple(passing),
        rejected=tuple(rejected),
        puzzles=puzzles,
        attempted=attempted,
    )


def print_and_maybe_save(
    label: str,
    candidates: tuple[tuple[TemplateEvaluation, Template], ...],
    out_dir: Path,
    save: bool,
    puzzles: dict[str, dict] | None = None,
    emit_puzzle: bool = False,
    puzzle_out: Path | None = None,
    frontend_out: Path | None = None,
) -> None:
    if not candidates:
        print(f"No {label} templates found.")
        return

    print(f"{label.capitalize()} templates:")
    for rank, (evaluation, template) in enumerate(candidates, start=1):
        path = out_dir / f"{template.id}.json"
        status = "pass" if evaluation.passed else "reject"
        if save:
            template.save(path)
            write_status = f"wrote {path}"
            if (
                rank == 1
                and emit_puzzle
                and puzzles is not None
                and template.id in puzzles
                and puzzle_out is not None
                and frontend_out is not None
            ):
                write_json(puzzle_out, puzzles[template.id])
                write_json(frontend_out, puzzles[template.id])
                write_status += f", wrote {puzzle_out} and {frontend_out}"
        else:
            write_status = "not saved"
        print(f"{rank}. {template.id}: {status}, score {evaluation.score}, {write_status}")
        print(f"   metrics: {evaluation.metrics}")
        if evaluation.reasons:
            print(f"   reasons: {', '.join(evaluation.reasons)}")


def main() -> None:
    default_config_path = Path("generator/template-config.json")
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", type=Path, default=default_config_path)
    config_args, _ = config_parser.parse_known_args()
    config = load_config(config_args.config)

    parser = argparse.ArgumentParser(
        description="Search randomized Swedish puzzle templates.",
        parents=[config_parser],
    )
    parser.add_argument(
        "--words",
        type=Path,
        default=Path(config_value(config, "words", "generator/data/dutch_words.csv")),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(config_value(config, "outDir", "generator/templates")),
    )
    parser.add_argument("--width", type=int, default=int(config_value(config, "width", 10)))
    parser.add_argument("--height", type=int, default=int(config_value(config, "height", 17)))
    parser.add_argument(
        "--attempts", type=int, default=int(config_value(config, "attempts", 200))
    )
    parser.add_argument("--seed", type=int, default=int(config_value(config, "seed", 1000)))
    parser.add_argument("--keep", type=int, default=int(config_value(config, "keep", 3)))
    parser.add_argument(
        "--max-word-length",
        type=int,
        default=int(config_value(config, "maxWordLength", 9)),
    )
    parser.add_argument(
        "--clue-directions",
        choices=("right", "down", "both"),
        default=config_value(config, "clueDirections", "both"),
        help="Allowed clue arrows. Answers always read right or down.",
    )
    parser.add_argument(
        "--max-clues-per-cell",
        type=int,
        choices=(1, 2),
        default=int(config_value(config, "maxCluesPerCell", 2)),
        help="Maximum clues in one clue cell. Two means one right and one down arrow.",
    )
    parser.add_argument(
        "--save-rejected",
        action=argparse.BooleanOptionalAction,
        default=bool(config_value(config, "saveRejected", False)),
        help="Also write the best rejected candidates for inspection.",
    )
    parser.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=bool(config_value(config, "verbose", False)),
        help="Print passing attempts as they are found.",
    )
    parser.add_argument(
        "--stop-when-enough-passing",
        action=argparse.BooleanOptionalAction,
        default=bool(config_value(config, "stopWhenEnoughPassing", False)),
        help="Stop searching after --keep passing templates have been found.",
    )
    parser.add_argument(
        "--require-fill",
        action=argparse.BooleanOptionalAction,
        default=bool(config_value(config, "requireFill", False)),
        help="Only accept templates that can generate at least one valid filled puzzle.",
    )
    parser.add_argument(
        "--fill-attempts",
        type=int,
        default=int(config_value(config, "fillAttempts", 25)),
        help="Number of fill attempts per geometrically passing template.",
    )
    parser.add_argument(
        "--fill-seed",
        type=int,
        default=int(config_value(config, "fillSeed", 7)),
        help="Base seed for fill checks.",
    )
    parser.add_argument(
        "--emit-puzzle",
        action=argparse.BooleanOptionalAction,
        default=bool(config_value(config, "emitPuzzle", False)),
        help="Write the best passing filled puzzle to the generator and frontend outputs.",
    )
    parser.add_argument(
        "--puzzle-out",
        type=Path,
        default=Path(config_value(config, "puzzleOut", "generated/puzzle.json")),
    )
    parser.add_argument(
        "--frontend-out",
        type=Path,
        default=Path(
            config_value(config, "frontendOut", "frontend/public/puzzles/puzzle.json")
        ),
    )
    args = parser.parse_args()
    quality = TemplateQualitySettings.from_config(config_value(config, "quality", {}))

    words = load_word_shapes(args.words, max_length=args.max_word_length)
    fill_words = load_words(args.words)
    allowed_directions: set[Direction]
    if args.clue_directions == "both":
        allowed_directions = {"right", "down"}
    else:
        allowed_directions = {args.clue_directions}

    results = search_templates(
        words=words,
        fill_words=fill_words,
        width=args.width,
        height=args.height,
        attempts=max(args.attempts, 1),
        seed=args.seed,
        keep=max(args.keep, 1),
        allowed_directions=allowed_directions,
        max_clues_per_cell=args.max_clues_per_cell,
        quality=quality,
        stop_when_enough_passing=args.stop_when_enough_passing,
        require_fill=args.require_fill,
        fill_attempts=args.fill_attempts,
        fill_seed=args.fill_seed,
        verbose=args.verbose,
    )

    print(f"Attempted {results.attempted} templates.")
    print_and_maybe_save(
        "passing",
        results.passing,
        args.out_dir,
        save=True,
        puzzles=results.puzzles,
        emit_puzzle=args.emit_puzzle,
        puzzle_out=args.puzzle_out,
        frontend_out=args.frontend_out,
    )
    print_and_maybe_save("rejected", results.rejected, args.out_dir, save=args.save_rejected)


if __name__ == "__main__":
    main()
