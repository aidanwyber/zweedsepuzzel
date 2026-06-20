from __future__ import annotations

import argparse
from dataclasses import dataclass
import itertools
import json
import math
from pathlib import Path
import shutil
from typing import Iterable

from generator.pdf_generator import solution_pdf_path


@dataclass(frozen=True)
class PuzzleCandidate:
    path: Path
    template_id: str
    title: str
    source_path: str | None
    words: frozenset[str]
    slots: tuple[dict, ...]

    @property
    def slot_count(self) -> int:
        return len(self.slots)

    @property
    def unique_word_count(self) -> int:
        return len(self.words)


def normalize_answer(value: object) -> str:
    return str(value or "").strip().upper()


def load_candidate(path: Path) -> PuzzleCandidate | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    slots = tuple(data.get("slots", ()))
    words = {
        normalize_answer(word)
        for word in data.get("words", ())
        if normalize_answer(word)
    }
    if not words and slots:
        words = {
            normalize_answer(slot.get("answer"))
            for slot in slots
            if normalize_answer(slot.get("answer"))
        }
    if not words:
        return None

    return PuzzleCandidate(
        path=path,
        template_id=str(data.get("templateId") or path.stem),
        title=str(data.get("title") or path.stem),
        source_path=data.get("sourcePath"),
        words=frozenset(words),
        slots=slots,
    )


def load_candidates(input_dir: Path, pattern: str) -> list[PuzzleCandidate]:
    candidates: list[PuzzleCandidate] = []
    for path in sorted(input_dir.glob(pattern)):
        if not path.is_file():
            continue
        candidate = load_candidate(path)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def pair_overlap(left: PuzzleCandidate, right: PuzzleCandidate) -> int:
    return len(left.words.intersection(right.words))


def collection_metrics(
    candidates: Iterable[PuzzleCandidate],
) -> tuple[int, int, int, list[dict]]:
    selected = tuple(candidates)
    total_overlap = 0
    max_overlap = 0
    union_words: set[str] = set()
    pairs: list[dict] = []

    for candidate in selected:
        union_words.update(candidate.words)

    for left, right in itertools.combinations(selected, 2):
        shared_words = sorted(left.words.intersection(right.words))
        shared_count = len(shared_words)
        total_overlap += shared_count
        max_overlap = max(max_overlap, shared_count)
        pairs.append(
            {
                "left": left.path.name,
                "right": right.path.name,
                "sharedWordCount": shared_count,
                "sharedWords": shared_words,
            }
        )

    return total_overlap, max_overlap, len(union_words), pairs


def collection_score(candidates: Iterable[PuzzleCandidate]) -> tuple[int, int, int, str]:
    selected = tuple(candidates)
    total_overlap, max_overlap, unique_word_count, _ = collection_metrics(selected)
    names = "|".join(candidate.path.name for candidate in selected)
    return total_overlap, max_overlap, -unique_word_count, names


def choose_exhaustive(
    candidates: list[PuzzleCandidate], size: int
) -> tuple[tuple[PuzzleCandidate, ...], str]:
    best = min(itertools.combinations(candidates, size), key=collection_score)
    return best, "exhaustive"


def greedy_from_start(
    candidates: list[PuzzleCandidate], size: int, start: PuzzleCandidate
) -> tuple[PuzzleCandidate, ...]:
    chosen = [start]
    remaining = [candidate for candidate in candidates if candidate != start]

    while len(chosen) < size:
        next_candidate = min(
            remaining,
            key=lambda candidate: (
                sum(pair_overlap(candidate, selected) for selected in chosen),
                max(pair_overlap(candidate, selected) for selected in chosen),
                -len(candidate.words.difference(*(selected.words for selected in chosen))),
                -candidate.unique_word_count,
                candidate.path.name,
            ),
        )
        chosen.append(next_candidate)
        remaining.remove(next_candidate)

    return tuple(chosen)


def improve_by_swapping(
    selected: tuple[PuzzleCandidate, ...],
    candidates: list[PuzzleCandidate],
) -> tuple[PuzzleCandidate, ...]:
    current = selected
    current_score = collection_score(current)

    improved = True
    while improved:
        improved = False
        selected_paths = {candidate.path for candidate in current}
        remaining = [
            candidate for candidate in candidates if candidate.path not in selected_paths
        ]
        for index in range(len(current)):
            for replacement in remaining:
                candidate_selection = list(current)
                candidate_selection[index] = replacement
                candidate_tuple = tuple(candidate_selection)
                candidate_score = collection_score(candidate_tuple)
                if candidate_score < current_score:
                    current = candidate_tuple
                    current_score = candidate_score
                    improved = True
                    break
            if improved:
                break

    return current


def choose_greedy(
    candidates: list[PuzzleCandidate], size: int
) -> tuple[tuple[PuzzleCandidate, ...], str]:
    starts = sorted(
        candidates,
        key=lambda candidate: (-candidate.unique_word_count, candidate.path.name),
    )
    best: tuple[PuzzleCandidate, ...] | None = None
    best_score: tuple[int, int, int, str] | None = None

    for start in starts:
        selected = improve_by_swapping(greedy_from_start(candidates, size, start), candidates)
        score = collection_score(selected)
        if best is None or best_score is None or score < best_score:
            best = selected
            best_score = score

    if best is None:
        raise ValueError("No candidate collection could be selected.")
    return best, "greedy-swap"


def choose_collection(
    candidates: list[PuzzleCandidate], size: int, exhaustive_limit: int
) -> tuple[tuple[PuzzleCandidate, ...], str]:
    if size < 1:
        raise ValueError("--size must be at least 1.")
    if size > len(candidates):
        raise ValueError(
            f"--size {size} is larger than the {len(candidates)} available candidates."
        )

    combination_count = math.comb(len(candidates), size)
    if combination_count <= exhaustive_limit:
        return choose_exhaustive(candidates, size)
    return choose_greedy(candidates, size)


def build_output(
    selected: tuple[PuzzleCandidate, ...],
    candidates: list[PuzzleCandidate],
    method: str,
) -> dict:
    total_overlap, max_overlap, unique_word_count, pairs = collection_metrics(selected)
    pair_count = len(pairs)
    return {
        "collectionSize": len(selected),
        "availableCandidateCount": len(candidates),
        "selectionMethod": method,
        "objective": "Minimize total pairwise shared answers, then max pairwise shared answers, then maximize unique answers.",
        "totalPairwiseSharedWords": total_overlap,
        "averagePairwiseSharedWords": (
            round(total_overlap / pair_count, 3) if pair_count else 0
        ),
        "maxPairwiseSharedWords": max_overlap,
        "uniqueWordCount": unique_word_count,
        "uniqueWords": sorted(set().union(*(candidate.words for candidate in selected))),
        "selected": [
            {
                "file": candidate.path.name,
                "sourcePath": candidate.source_path,
                "templateId": candidate.template_id,
                "title": candidate.title,
                "slotCount": candidate.slot_count,
                "uniqueWordCount": candidate.unique_word_count,
                "words": sorted(candidate.words),
            }
            for candidate in selected
        ],
        "pairwiseOverlaps": pairs,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def reset_directory(path: Path) -> None:
    resolved = path.resolve()
    if resolved == resolved.parent:
        raise ValueError(f"Refusing to empty unsafe directory: {path}")

    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def selected_pdf_paths(candidate: PuzzleCandidate) -> list[Path]:
    if not candidate.source_path:
        return []

    puzzle_pdf = Path(candidate.source_path)
    if puzzle_pdf.suffix.lower() != ".pdf" or not puzzle_pdf.exists():
        return []

    paths = [puzzle_pdf]
    solution_pdf = solution_pdf_path(puzzle_pdf)
    if solution_pdf.exists():
        paths.append(solution_pdf)
    return paths


def copy_selected_pdfs(
    selected: tuple[PuzzleCandidate, ...], selection_dir: Path
) -> list[str]:
    reset_directory(selection_dir)
    copied: list[str] = []
    used_names: set[str] = set()

    for candidate in selected:
        for source in selected_pdf_paths(candidate):
            target_name = source.name
            if target_name in used_names:
                target_name = f"{candidate.path.stem}-{source.name}"
            used_names.add(target_name)
            target = selection_dir / target_name
            shutil.copy2(source, target)
            copied.append(str(target))

    return copied


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select a collection of generated puzzles with minimal shared words."
    )
    parser.add_argument("--input-dir", type=Path, default=Path("output/json"))
    parser.add_argument("--pattern", default="*.json")
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Collection JSON output path. Defaults to output/json/collection-<size>.json.",
    )
    parser.add_argument(
        "--exhaustive-limit",
        type=int,
        default=200_000,
        help="Maximum combination count to evaluate exhaustively before using greedy-swap.",
    )
    parser.add_argument(
        "--selection-pdf-dir",
        type=Path,
        default=Path("output/pdf/selection"),
        help="Empty this directory and copy selected puzzle and solution PDFs into it.",
    )
    args = parser.parse_args()

    candidates = load_candidates(args.input_dir, args.pattern)
    selected, method = choose_collection(candidates, args.size, args.exhaustive_limit)
    output = build_output(selected, candidates, method)
    copied_pdfs = copy_selected_pdfs(selected, args.selection_pdf_dir)
    output["selectionPdfDir"] = str(args.selection_pdf_dir)
    output["copiedPdfs"] = copied_pdfs
    out_path = args.out or args.input_dir / f"collection-{args.size}.json"
    write_json(out_path, output)

    print(
        f"Selected {len(selected)}/{len(candidates)} puzzles with "
        f"{output['totalPairwiseSharedWords']} total shared words "
        f"({method}); wrote {out_path}."
    )
    print(f"Copied {len(copied_pdfs)} PDFs to {args.selection_pdf_dir}.")
    for candidate in selected:
        print(f"- {candidate.path.name}: {candidate.unique_word_count} unique words")


if __name__ == "__main__":
    main()
