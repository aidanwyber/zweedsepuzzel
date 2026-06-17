from __future__ import annotations

import argparse
import random
import re
from dataclasses import dataclass, replace
from pathlib import Path

from generator.config import config_value, load_config
from generator.generate import DRAFT_PROFILE, generate_best_candidate, load_words, write_json
from generator.template import Direction, Slot, Template
from generator.word_csv import read_word_rows


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
class SearchHeuristicSettings:
    beam_width: int = 1
    branching_factor: int = 1
    placement_steps: int = 90
    candidate_pool: int = 60
    randomness: float = 0.08
    interlock_weight: float = 36.0
    fill_weight: float = 28.0
    slot_weight: float = 16.0
    clue_weight: float = 8.0
    domain_weight: float = 8.0
    short_slot_penalty: float = 6.0
    length_weight: float = 0.2
    densify_passes: int = 0
    densify_candidate_pool: int = 80
    densify_min_gain: float = 0.001

    @classmethod
    def from_config(cls, config: dict) -> SearchHeuristicSettings:
        return cls(
            beam_width=max(1, int(config_value(config, "beamWidth", cls.beam_width))),
            branching_factor=max(
                1, int(config_value(config, "branchingFactor", cls.branching_factor))
            ),
            placement_steps=max(
                1, int(config_value(config, "placementSteps", cls.placement_steps))
            ),
            candidate_pool=max(1, int(config_value(config, "candidatePool", cls.candidate_pool))),
            randomness=max(0.0, float(config_value(config, "randomness", cls.randomness))),
            interlock_weight=float(
                config_value(config, "interlockWeight", cls.interlock_weight)
            ),
            fill_weight=float(config_value(config, "fillWeight", cls.fill_weight)),
            slot_weight=float(config_value(config, "slotWeight", cls.slot_weight)),
            clue_weight=float(config_value(config, "clueWeight", cls.clue_weight)),
            domain_weight=float(config_value(config, "domainWeight", cls.domain_weight)),
            short_slot_penalty=float(
                config_value(config, "shortSlotPenalty", cls.short_slot_penalty)
            ),
            length_weight=float(config_value(config, "lengthWeight", cls.length_weight)),
            densify_passes=max(0, int(config_value(config, "densifyPasses", cls.densify_passes))),
            densify_candidate_pool=max(
                1,
                int(config_value(config, "densifyCandidatePool", cls.densify_candidate_pool)),
            ),
            densify_min_gain=max(
                0.0,
                float(config_value(config, "densifyMinGain", cls.densify_min_gain)),
            ),
        )


@dataclass(frozen=True)
class SearchResults:
    passing: tuple[tuple[TemplateEvaluation, Template], ...]
    rejected: tuple[tuple[TemplateEvaluation, Template], ...]
    puzzles: dict[str, dict]
    attempted: int
    interrupted: bool = False


@dataclass(frozen=True)
class PartialTemplateState:
    board: dict[tuple[int, int], str]
    clues: dict[tuple[int, int], set[Direction]]
    reserved_stops: set[tuple[int, int]]
    reserved_blocks: set[tuple[int, int]]
    used: set[str]
    slots: list[Placement]
    score: float = 0.0


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
    for answer, _ in read_word_rows(path):
        normalized_answer = answer.upper()
        letters = tokenize(answer)
        if 3 <= len(letters) <= max_length and normalized_answer not in seen:
            seen.add(normalized_answer)
            words.append(WordShape(answer=normalized_answer, letters=letters))
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


def empty_state() -> PartialTemplateState:
    return PartialTemplateState(
        board={},
        clues={},
        reserved_stops=set(),
        reserved_blocks=set(),
        used=set(),
        slots=[],
    )


def place_in_state(
    state: PartialTemplateState,
    placement: Placement,
    width: int,
    height: int,
    score: float = 0.0,
) -> PartialTemplateState:
    board, clues, reserved_stops, reserved_blocks, used, slots = place(
        state.board,
        state.clues,
        state.reserved_stops,
        state.reserved_blocks,
        state.used,
        state.slots,
        placement,
        width,
        height,
    )
    return PartialTemplateState(
        board=board,
        clues=clues,
        reserved_stops=reserved_stops,
        reserved_blocks=reserved_blocks,
        used=used,
        slots=slots,
        score=score,
    )


def cell_occupancy(slots: list[Placement]) -> dict[tuple[int, int], int]:
    occupancy: dict[tuple[int, int], int] = {}
    for slot in slots:
        for cell in slot.cells:
            occupancy[cell] = occupancy.get(cell, 0) + 1
    return occupancy


def clue_score(clue_cell_ratio: float, quality: TemplateQualitySettings) -> float:
    if quality.min_clue_cell_ratio <= clue_cell_ratio <= quality.max_clue_cell_ratio:
        return 1.0
    if clue_cell_ratio < quality.min_clue_cell_ratio:
        distance = quality.min_clue_cell_ratio - clue_cell_ratio
    else:
        distance = clue_cell_ratio - quality.max_clue_cell_ratio
    return max(0.0, 1.0 - distance / max(quality.max_clue_cell_ratio, 0.01))


def score_partial_state(
    state: PartialTemplateState,
    width: int,
    height: int,
    quality: TemplateQualitySettings,
    heuristics: SearchHeuristicSettings,
    length_counts: dict[int, int],
) -> float:
    total_cells = width * height
    if not state.board or total_cells == 0:
        return 0.0

    occupancy = cell_occupancy(state.slots)
    fill_rate = len(state.board) / total_cells
    interlock_ratio = (
        sum(1 for count in occupancy.values() if count > 1) / len(state.board)
        if state.board
        else 0.0
    )
    slot_ratio = min(len(state.slots) / max(quality.target_slot_count, 1), 1.0)
    clue_cell_ratio = len(state.clues) / total_cells
    short_slot_ratio = (
        sum(1 for slot in state.slots if len(slot.cells) <= 3) / len(state.slots)
        if state.slots
        else 0.0
    )
    domain_score = (
        sum(min(length_counts.get(len(slot.cells), 0) / 6, 1.0) for slot in state.slots)
        / len(state.slots)
        if state.slots
        else 0.0
    )

    return (
        fill_rate * heuristics.fill_weight
        + interlock_ratio * heuristics.interlock_weight
        + slot_ratio * heuristics.slot_weight
        + clue_score(clue_cell_ratio, quality) * heuristics.clue_weight
        + domain_score * heuristics.domain_weight
        - short_slot_ratio * heuristics.short_slot_penalty
    )


def score_candidate_placement(
    state: PartialTemplateState,
    placement: Placement,
    width: int,
    height: int,
    quality: TemplateQualitySettings,
    heuristics: SearchHeuristicSettings,
    length_counts: dict[int, int],
) -> float:
    next_state = place_in_state(state, placement, width, height)
    intersections = sum(1 for cell in placement.cells if cell in state.board)
    new_cells = sum(1 for cell in placement.cells if cell not in state.board)
    dual_clue_bonus = 1 if placement.origin in state.clues else 0
    domain_support = min(length_counts.get(placement.word.length, 0) / 6, 1.0)
    return (
        score_partial_state(next_state, width, height, quality, heuristics, length_counts)
        + intersections * 4.0
        + new_cells * 0.4
        + dual_clue_bonus * 2.0
        + domain_support * heuristics.domain_weight
        + placement.word.length * heuristics.length_weight
    )


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


def ranked_placements_for_state(
    state: PartialTemplateState,
    placements: list[Placement],
    indexed: dict[tuple[tuple[int, int], str], list[Placement]],
    width: int,
    height: int,
    max_clues_per_cell: int,
    quality: TemplateQualitySettings,
    heuristics: SearchHeuristicSettings,
    length_counts: dict[int, int],
    randomizer: random.Random,
) -> list[tuple[float, Placement]]:
    ranked = []
    for placement in candidate_placements(state.board, placements, indexed):
        if not can_place(
            state.board,
            state.clues,
            state.reserved_stops,
            state.reserved_blocks,
            state.used,
            state.slots,
            placement,
            width,
            height,
            max_clues_per_cell,
        ):
            continue
        intersections = sum(1 for cell in placement.cells if cell in state.board)
        if state.slots and intersections == 0:
            continue
        score = score_candidate_placement(
            state,
            placement,
            width,
            height,
            quality,
            heuristics,
            length_counts,
        )
        if heuristics.randomness:
            score += randomizer.uniform(-heuristics.randomness, heuristics.randomness)
        ranked.append((score, placement))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[: heuristics.candidate_pool]


def build_slots_with_beam(
    placements: list[Placement],
    indexed: dict[tuple[tuple[int, int], str], list[Placement]],
    width: int,
    height: int,
    max_clues_per_cell: int,
    quality: TemplateQualitySettings,
    heuristics: SearchHeuristicSettings,
    length_counts: dict[int, int],
    randomizer: random.Random,
) -> PartialTemplateState:
    beam = [empty_state()]
    best_state = beam[0]

    for _ in range(heuristics.placement_steps):
        expanded: list[PartialTemplateState] = []
        for state in beam:
            ranked = ranked_placements_for_state(
                state,
                placements,
                indexed,
                width,
                height,
                max_clues_per_cell,
                quality,
                heuristics,
                length_counts,
                randomizer,
            )
            for candidate_score, placement in ranked[: heuristics.branching_factor]:
                next_state = place_in_state(
                    state,
                    placement,
                    width,
                    height,
                    score=candidate_score,
                )
                expanded.append(next_state)

        if not expanded:
            break

        expanded.sort(key=lambda state: state.score, reverse=True)
        beam = expanded[: heuristics.beam_width]
        if beam[0].score >= best_state.score:
            best_state = beam[0]

    return best_state


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


def promoted_template_from_state(
    state: PartialTemplateState,
    width: int,
    height: int,
    template_id: str,
    title: str,
    max_clues_per_cell: int,
    allowed_answers: set[str],
) -> Template:
    template = slots_to_template(
        slots=state.slots,
        width=width,
        height=height,
        template_id=template_id,
        title=title,
    )
    return promote_readable_runs(
        template,
        max_clues_per_cell=max_clues_per_cell,
        board=state.board,
        allowed_answers=allowed_answers,
        used_answers=state.used,
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


def should_accept_densified(
    current: TemplateEvaluation, candidate: TemplateEvaluation, min_gain: float
) -> bool:
    if candidate.passed and not current.passed:
        return True
    if current.passed and not candidate.passed:
        return False
    return candidate.score > current.score + min_gain


def densify_state_by_score(
    state: PartialTemplateState,
    placements: list[Placement],
    indexed: dict[tuple[tuple[int, int], str], list[Placement]],
    width: int,
    height: int,
    template_id: str,
    title: str,
    max_clues_per_cell: int,
    quality: TemplateQualitySettings,
    heuristics: SearchHeuristicSettings,
    length_counts: dict[int, int],
    allowed_answers: set[str],
    words: list[WordShape],
    randomizer: random.Random,
) -> tuple[PartialTemplateState, Template, TemplateEvaluation]:
    current_state = state
    current_template = promoted_template_from_state(
        current_state,
        width,
        height,
        template_id,
        title,
        max_clues_per_cell,
        allowed_answers,
    )
    current_evaluation = evaluate_template(
        current_template,
        words,
        max_clues_per_cell=max_clues_per_cell,
        quality=quality,
    )

    for _ in range(heuristics.densify_passes):
        ranked = ranked_placements_for_state(
            current_state,
            placements,
            indexed,
            width,
            height,
            max_clues_per_cell,
            quality,
            heuristics,
            length_counts,
            randomizer,
        )

        best_candidate: tuple[PartialTemplateState, Template, TemplateEvaluation] | None = None
        for _, placement in ranked[: heuristics.densify_candidate_pool]:
            candidate_state = place_in_state(current_state, placement, width, height)
            candidate_template = promoted_template_from_state(
                candidate_state,
                width,
                height,
                template_id,
                title,
                max_clues_per_cell,
                allowed_answers,
            )
            candidate_evaluation = evaluate_template(
                candidate_template,
                words,
                max_clues_per_cell=max_clues_per_cell,
                quality=quality,
            )
            if not should_accept_densified(
                current_evaluation,
                candidate_evaluation,
                heuristics.densify_min_gain,
            ):
                continue
            if (
                best_candidate is None
                or candidate_evaluation.score > best_candidate[2].score
                or (candidate_evaluation.passed and not best_candidate[2].passed)
            ):
                best_candidate = (candidate_state, candidate_template, candidate_evaluation)

        if best_candidate is None:
            break

        current_state, current_template, current_evaluation = best_candidate

    return current_state, current_template, current_evaluation


def finalize_search_results(
    passing: list[tuple[TemplateEvaluation, Template]],
    rejected: list[tuple[TemplateEvaluation, Template]],
    puzzles: dict[str, dict],
    keep: int,
    attempted: int,
    interrupted: bool = False,
) -> SearchResults:
    passing.sort(key=lambda item: item[0].score, reverse=True)
    rejected.sort(key=lambda item: item[0].score, reverse=True)
    best_passing = tuple(passing[:keep])
    best_ids = {template.id for _, template in best_passing}
    best_puzzles = {
        template_id: puzzle
        for template_id, puzzle in puzzles.items()
        if template_id in best_ids
    }

    return SearchResults(
        passing=best_passing,
        rejected=tuple(rejected[:keep]),
        puzzles=best_puzzles,
        attempted=attempted,
        interrupted=interrupted,
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
    heuristics: SearchHeuristicSettings,
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
    length_counts: dict[int, int] = {}
    for word in words:
        length_counts[word.length] = length_counts.get(word.length, 0) + 1
    indexed = placement_index(placements)
    passing: list[tuple[TemplateEvaluation, Template]] = []
    rejected: list[tuple[TemplateEvaluation, Template]] = []
    puzzles: dict[str, dict] = {}
    attempted = 0

    try:
        for attempt in range(attempts):
            attempted += 1
            attempt_seed = seed + attempt
            randomizer = random.Random(attempt_seed)
            state = build_slots_with_beam(
                placements=placements,
                indexed=indexed,
                width=width,
                height=height,
                max_clues_per_cell=max_clues_per_cell,
                quality=quality,
                heuristics=heuristics,
                length_counts=length_counts,
                randomizer=randomizer,
            )
            template_id = f"random-{width}x{height}-{attempt_seed}"
            title = f"Randomized {width}x{height} template {attempt_seed}"
            state, template, evaluation = densify_state_by_score(
                state,
                placements,
                indexed,
                width,
                height,
                template_id,
                title,
                max_clues_per_cell,
                quality,
                heuristics,
                length_counts,
                allowed_answers,
                words,
                randomizer,
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
            if not evaluation.passed or stop_when_enough_passing:
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
    except KeyboardInterrupt:
        return finalize_search_results(
            passing=passing,
            rejected=rejected,
            puzzles=puzzles,
            keep=keep,
            attempted=attempted,
            interrupted=True,
        )

    return finalize_search_results(
        passing=passing,
        rejected=rejected,
        puzzles=puzzles,
        keep=keep,
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
    default_config_path = Path("generator/config.json")
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", type=Path, default=default_config_path)
    config_args, _ = config_parser.parse_known_args()
    root_config = load_config(config_args.config)
    config = config_value(root_config, "templateSearch", {})

    parser = argparse.ArgumentParser(
        description="Search randomized Swedish puzzle templates.",
        parents=[config_parser],
    )
    parser.add_argument(
        "--words",
        type=Path,
        default=Path(config_value(root_config, "words", "generator/data/peter_words.csv")),
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
    heuristic_config = config_value(config, "heuristics", {})
    parser.add_argument(
        "--beam-width",
        type=int,
        default=int(config_value(heuristic_config, "beamWidth", SearchHeuristicSettings.beam_width)),
        help="Number of partial template states kept at each construction step.",
    )
    parser.add_argument(
        "--branching-factor",
        type=int,
        default=int(
            config_value(
                heuristic_config,
                "branchingFactor",
                SearchHeuristicSettings.branching_factor,
            )
        ),
        help="Number of candidate placements expanded per beam state.",
    )
    parser.add_argument(
        "--placement-steps",
        type=int,
        default=int(
            config_value(
                heuristic_config,
                "placementSteps",
                SearchHeuristicSettings.placement_steps,
            )
        ),
        help="Maximum placement steps per template attempt.",
    )
    parser.add_argument(
        "--candidate-pool",
        type=int,
        default=int(
            config_value(
                heuristic_config,
                "candidatePool",
                SearchHeuristicSettings.candidate_pool,
            )
        ),
        help="Maximum ranked candidate placements considered per beam state.",
    )
    parser.add_argument(
        "--randomness",
        type=float,
        default=float(
            config_value(heuristic_config, "randomness", SearchHeuristicSettings.randomness)
        ),
        help="Small score jitter used to diversify repeated attempts.",
    )
    parser.add_argument(
        "--densify-passes",
        type=int,
        default=int(
            config_value(
                heuristic_config,
                "densifyPasses",
                SearchHeuristicSettings.densify_passes,
            )
        ),
        help="Greedy post-construction passes that only accept exact score improvements.",
    )
    parser.add_argument(
        "--densify-candidate-pool",
        type=int,
        default=int(
            config_value(
                heuristic_config,
                "densifyCandidatePool",
                SearchHeuristicSettings.densify_candidate_pool,
            )
        ),
        help="Number of ranked placements checked during each densification pass.",
    )
    parser.add_argument(
        "--densify-min-gain",
        type=float,
        default=float(
            config_value(
                heuristic_config,
                "densifyMinGain",
                SearchHeuristicSettings.densify_min_gain,
            )
        ),
        help="Minimum exact template score gain required to accept a densification move.",
    )
    args = parser.parse_args()
    quality = TemplateQualitySettings.from_config(config_value(config, "quality", {}))
    base_heuristics = SearchHeuristicSettings.from_config(heuristic_config)
    heuristics = replace(
        base_heuristics,
        beam_width=max(args.beam_width, 1),
        branching_factor=max(args.branching_factor, 1),
        placement_steps=max(args.placement_steps, 1),
        candidate_pool=max(args.candidate_pool, 1),
        randomness=max(args.randomness, 0.0),
        densify_passes=max(args.densify_passes, 0),
        densify_candidate_pool=max(args.densify_candidate_pool, 1),
        densify_min_gain=max(args.densify_min_gain, 0.0),
    )

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
        heuristics=heuristics,
        stop_when_enough_passing=args.stop_when_enough_passing,
        require_fill=args.require_fill,
        fill_attempts=args.fill_attempts,
        fill_seed=args.fill_seed,
        verbose=args.verbose,
    )

    if results.interrupted:
        print(
            "Interrupted; using the best templates collected before the current attempt."
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
