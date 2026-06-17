from __future__ import annotations

import argparse
import csv
import random
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent
# DEFAULT_INPUT = DATA_DIR / "nouns-meervouden.txt"
DEFAULT_INPUT = DATA_DIR / "basiswoorden-gekeurd.txt"
DEFAULT_OUTPUT = DATA_DIR / "test_words.csv"
DEFAULT_COUNT = 1000
DEFAULT_SEED = 7
DEFAULT_MIN_LENGTH = 2
DEFAULT_MAX_LENGTH = 17
DEFAULT_MIN_PER_LENGTH = 12


def normalize_word(raw_word: str) -> str:
    decomposed = unicodedata.normalize("NFKD", raw_word.strip().casefold())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def puzzle_length(word: str) -> int:
    """Count letters the same way the puzzle does, with IJ as one letter."""
    normalized = word.upper()
    length = 0
    index = 0
    while index < len(normalized):
        if normalized[index : index + 2] == "IJ":
            index += 2
        else:
            index += 1
        length += 1
    return length


def load_words(path: Path, min_length: int, max_length: int) -> list[str]:
    seen: set[str] = set()
    words: list[str] = []

    with path.open(encoding="utf-8") as source:
        for line in source:
            word = normalize_word(line)
            if not word or word in seen:
                continue

            # The generator currently tokenizes only A-Z and IJ. Normalize
            # accented letters to the main alphabet before filtering.
            if not re.fullmatch(r"[a-z]+", word):
                continue

            length = puzzle_length(word)
            if min_length <= length <= max_length:
                seen.add(word)
                words.append(word)

    return words


def choose_words(
    words: list[str], count: int, seed: int, min_per_length: int
) -> list[str]:
    if count >= len(words):
        return sorted(words)

    rng = random.Random(seed)
    if min_per_length < 1:
        return sorted(rng.sample(words, count))

    groups: dict[int, list[str]] = defaultdict(list)
    for word in words:
        groups[puzzle_length(word)].append(word)

    for length_words in groups.values():
        rng.shuffle(length_words)

    if count < len(groups):
        return sorted(rng.sample(words, count))

    selected: list[str] = []
    selected_per_length = {length: 0 for length in groups}

    for length in sorted(groups):
        selected.append(groups[length].pop())
        selected_per_length[length] += 1

    while len(selected) < count:
        changed = False
        for length in sorted(groups):
            if len(selected) >= count:
                break
            if not groups[length] or selected_per_length[length] >= min_per_length:
                continue
            selected.append(groups[length].pop())
            selected_per_length[length] += 1
            changed = True
        if not changed:
            break

    remaining = [word for length_words in groups.values() for word in length_words]
    selected.extend(rng.sample(remaining, count - len(selected)))
    return sorted(selected)


def write_word_list(path: Path, words: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(("answer", "description"))
        for index, word in enumerate(words, start=1):
            writer.writerow((word, f"test{index:04d}"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a deterministic CSV test word list from plural Dutch nouns."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--min-length", type=int, default=DEFAULT_MIN_LENGTH)
    parser.add_argument("--max-length", type=int, default=DEFAULT_MAX_LENGTH)
    parser.add_argument(
        "--min-per-length",
        type=int,
        default=DEFAULT_MIN_PER_LENGTH,
        help="Minimum words to reserve per puzzle length when enough rows are requested.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.count < 1:
        raise SystemExit("--count must be at least 1")
    if args.min_length < 1:
        raise SystemExit("--min-length must be at least 1")
    if args.max_length < args.min_length:
        raise SystemExit("--max-length must be greater than or equal to --min-length")
    if args.min_per_length < 0:
        raise SystemExit("--min-per-length must be at least 0")

    words = load_words(args.input, args.min_length, args.max_length)
    selected_words = choose_words(words, args.count, args.seed, args.min_per_length)
    write_word_list(args.output, selected_words)

    print(
        f"Wrote {len(selected_words)} words to {args.output} "
        f"from {len(words)} eligible source words."
    )


if __name__ == "__main__":
    main()
