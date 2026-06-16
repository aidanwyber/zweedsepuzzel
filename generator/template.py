from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Direction = Literal["right", "down"]


@dataclass(frozen=True)
class Slot:
    id: str
    direction: Direction
    origin: tuple[int, int]
    cells: tuple[tuple[int, int], ...]

    @property
    def length(self) -> int:
        return len(self.cells)

    def stop_cell(self) -> tuple[int, int] | None:
        if not self.cells:
            return None
        row, col = self.cells[-1]
        if self.direction == "right":
            return row, col + 1
        return row + 1, col

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "direction": self.direction,
            "origin": list(self.origin),
            "cells": [list(cell) for cell in self.cells],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Slot:
        return cls(
            id=data["id"],
            direction=data["direction"],
            origin=tuple(data["origin"]),
            cells=tuple(tuple(cell) for cell in data["cells"]),
        )


@dataclass(frozen=True)
class Overlap:
    a_slot: str
    a_index: int
    b_slot: str
    b_index: int


@dataclass(frozen=True)
class Template:
    id: str
    title: str
    width: int
    height: int
    slots: tuple[Slot, ...]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "width": self.width,
            "height": self.height,
            "slots": [slot.to_dict() for slot in self.slots],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Template:
        return cls(
            id=data["id"],
            title=data["title"],
            width=int(data["width"]),
            height=int(data["height"]),
            slots=tuple(Slot.from_dict(slot) for slot in data["slots"]),
        )

    @classmethod
    def load(cls, path: Path) -> Template:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def load_many(cls, directory: Path) -> dict[str, Template]:
        templates: dict[str, Template] = {}
        if not directory.exists():
            return templates

        for path in sorted(directory.glob("*.json")):
            template = cls.load(path)
            templates[template.id] = template
        return templates

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def derive_overlaps(self) -> list[Overlap]:
        by_cell: dict[tuple[int, int], list[tuple[str, int]]] = {}
        for slot in self.slots:
            for index, cell in enumerate(slot.cells):
                by_cell.setdefault(cell, []).append((slot.id, index))

        overlaps: list[Overlap] = []
        for occupants in by_cell.values():
            for left_index, left in enumerate(occupants):
                for right in occupants[left_index + 1 :]:
                    overlaps.append(Overlap(left[0], left[1], right[0], right[1]))
                    overlaps.append(Overlap(right[0], right[1], left[0], left[1]))
        return overlaps

    def connected_components(self) -> int:
        slot_ids = {slot.id for slot in self.slots}
        if not slot_ids:
            return 0

        adjacency: dict[str, set[str]] = {slot_id: set() for slot_id in slot_ids}
        for overlap in self.derive_overlaps():
            adjacency[overlap.a_slot].add(overlap.b_slot)

        components = 0
        seen: set[str] = set()
        for slot_id in slot_ids:
            if slot_id in seen:
                continue
            components += 1
            stack = [slot_id]
            seen.add(slot_id)
            while stack:
                current = stack.pop()
                for neighbor in adjacency[current]:
                    if neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
        return components

    def letter_cells(self) -> set[tuple[int, int]]:
        return {cell for slot in self.slots for cell in slot.cells}

    def clue_cells(self) -> set[tuple[int, int]]:
        return {slot.origin for slot in self.slots}

    def unterminated_slots(self) -> list[tuple[str, tuple[int, int]]]:
        letter_cells = self.letter_cells()
        clue_cells = self.clue_cells()
        invalid = []

        for slot in self.slots:
            stop_cell = slot.stop_cell()
            if stop_cell is None:
                continue
            row, col = stop_cell
            if row < 0 or row >= self.height or col < 0 or col >= self.width:
                continue
            if stop_cell in clue_cells:
                continue
            if stop_cell in letter_cells:
                invalid.append((slot.id, stop_cell))

        return invalid


def derive_overlaps(slots: tuple[Slot, ...]) -> list[Overlap]:
    return Template("_anonymous", "Anonymous", 0, 0, slots).derive_overlaps()


def connected_components(slots: tuple[Slot, ...], overlaps: list[Overlap]) -> int:
    slot_ids = {slot.id for slot in slots}
    if not slot_ids:
        return 0

    adjacency: dict[str, set[str]] = {slot_id: set() for slot_id in slot_ids}
    for overlap in overlaps:
        adjacency[overlap.a_slot].add(overlap.b_slot)

    components = 0
    seen: set[str] = set()
    for slot_id in slot_ids:
        if slot_id in seen:
            continue
        components += 1
        stack = [slot_id]
        seen.add(slot_id)
        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
    return components
