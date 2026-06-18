from __future__ import annotations


VOWELS = frozenset("aeiouyáàäâéèëêíìïîóòöôúùüû")
VOWEL_GROUPS = (
    "aai",
    "eeu",
    "ieu",
    "oei",
    "ooi",
    "eie",
    "aa",
    "ee",
    "oo",
    "uu",
    "ie",
    "ij",
    "ei",
    "ui",
    "au",
    "ou",
    "eu",
    "oe",
)
START_CLUSTERS = frozenset(
    (
        "bl",
        "br",
        "ch",
        "cl",
        "cr",
        "dr",
        "dw",
        "fl",
        "fr",
        "gl",
        "gr",
        "kl",
        "kn",
        "kr",
        "kw",
        "pl",
        "pr",
        "sch",
        "schr",
        "scr",
        "sl",
        "sm",
        "sn",
        "sp",
        "spr",
        "st",
        "str",
        "tr",
        "tw",
        "vl",
        "vr",
        "wr",
        "zw",
    )
)
MIN_PREFIX = 2
MIN_SUFFIX = 2


def hyphenation_points(word: str) -> list[int]:
    """Return Dutch-style hyphenation positions for one alphabetic word.

    This is a deterministic heuristic for puzzle clue labels, not a full
    TeX-pattern hyphenator. It follows the useful Dutch layout rules for this
    project: keep vowel groups together, avoid one-letter fragments, split
    between vowel groups through the intervening consonant cluster, and keep
    common Dutch onset clusters together where possible.
    """
    normalized = word.casefold()
    if len(normalized) < MIN_PREFIX + MIN_SUFFIX + 1:
        return []

    points: set[int] = set()
    vowel_spans = _vowel_spans(normalized)
    for left, right in zip(vowel_spans, vowel_spans[1:]):
        cluster_start = left[1]
        cluster_end = right[0]
        if cluster_end < cluster_start:
            continue

        cluster = normalized[cluster_start:cluster_end]
        if not cluster:
            point = cluster_start
        elif len(cluster) == 1:
            point = cluster_start
        else:
            point = _split_consonant_cluster(normalized, cluster_start, cluster_end)

        if MIN_PREFIX <= point <= len(normalized) - MIN_SUFFIX:
            points.add(point)

    return sorted(points)


def hyphenate_word(word: str) -> list[str]:
    points = hyphenation_points(word)
    if not points:
        return [word]

    parts: list[str] = []
    start = 0
    for point in points:
        parts.append(word[start:point])
        start = point
    parts.append(word[start:])
    return [part for part in parts if part]


def split_word_for_width(word: str, fits) -> list[str]:
    """Split a single word into display chunks using Dutch hyphenation.

    `fits` is a callback receiving a candidate string and returning whether it
    fits the available line width.
    """
    if fits(word):
        return [word]

    parts = hyphenate_word(word)
    if len(parts) == 1:
        return _hard_split_word(word, fits)

    chunks: list[str] = []
    index = 0
    while index < len(parts):
        chunk = parts[index]
        next_index = index + 1
        while next_index < len(parts):
            candidate = chunk + parts[next_index]
            has_more_after_candidate = next_index + 1 < len(parts)
            display_candidate = candidate + ("-" if has_more_after_candidate else "")
            if not fits(display_candidate):
                break
            chunk = candidate
            next_index += 1

        display = chunk + ("-" if next_index < len(parts) else "")
        if fits(display):
            chunks.append(display)
            index = next_index
            continue

        fallback = _hard_split_word(chunk, fits, force_hyphen=next_index < len(parts))
        chunks.extend(fallback)
        index = next_index

    return chunks


def _vowel_spans(word: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(word):
        if word[index] not in VOWELS:
            index += 1
            continue

        matched = None
        for group in VOWEL_GROUPS:
            if word.startswith(group, index):
                matched = group
                break
        end = index + len(matched) if matched else index + 1
        while end < len(word) and word[end] in VOWELS:
            end += 1
        spans.append((index, end))
        index = end
    return spans


def _split_consonant_cluster(word: str, start: int, end: int) -> int:
    cluster = word[start:end]
    for offset in range(0, len(cluster)):
        suffix = cluster[offset:]
        if suffix in START_CLUSTERS:
            return start + offset
    return end - 1


def _hard_split_word(word: str, fits, force_hyphen: bool = False) -> list[str]:
    chunks: list[str] = []
    current = ""
    for character in word:
        candidate = current + character
        display_candidate = candidate + "-" if force_hyphen else candidate
        if current and not fits(display_candidate):
            chunks.append(current + ("-" if force_hyphen else ""))
            current = character
        else:
            current = candidate
    if current:
        chunks.append(current + ("-" if force_hyphen else ""))
    return chunks
