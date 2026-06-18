from __future__ import annotations

import argparse
from functools import lru_cache
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from generator.dutch_hyphenation import split_word_for_width


MM_TO_PT = 72 / 25.4
A5_WIDTH_PT = 148 * MM_TO_PT
A5_HEIGHT_PT = 210 * MM_TO_PT
DEFAULT_MARGIN_PT = 9 * MM_TO_PT
STROKE_WIDTH = 0.15 * MM_TO_PT
BLOCK_GRAY_VALUE = 0.67
CLUE_GRAY_VALUE = 0.85
FONT_SIZE = 8
MIN_FONT_SIZE = 6.25
MIN_MULTI_CLUE_LINES = 2
ARROW_MARGIN_PT = 2 * MM_TO_PT
TEXT_PADDING_PT = 1.4
TEXT_GAP_PT = 0.8
LINE_HEIGHT_RATIO = 1.0
ARROW_WIDTH_PT = 6
ARROW_HEIGHT_PT = 6

Direction = Literal["right", "down"]


def pdf_path_for_template(path: Path, template_id: str | None) -> Path:
    if not template_id:
        return path

    safe_template_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", template_id).strip("-")
    if not safe_template_id:
        return path

    suffix = path.suffix or ".pdf"
    return path.with_name(f"{path.stem}-{safe_template_id}{suffix}")


@dataclass(frozen=True)
class FitGrid:
    x: float
    y: float
    width: float
    height: float
    cell: float
    gap: float
    border: float


@dataclass(frozen=True)
class ClueFitIssue:
    row: int
    col: int
    slot_id: str | None
    text: str
    required_lines: int
    available_lines: int


class PdfContent:
    def __init__(self) -> None:
        self.parts: list[bytes] = []

    def raw(self, value: str) -> None:
        self.parts.append(value.encode("ascii"))

    def gray_fill(self, value: float) -> None:
        self.raw(f"{value:.25f} g\n")

    def gray_stroke(self, value: float) -> None:
        self.raw(f"{value:.25f} G\n")

    def rect(self, x: float, y: float, width: float, height: float, fill: bool = True) -> None:
        operator = "f" if fill else "S"
        self.raw(f"{x:.3f} {y:.3f} {width:.3f} {height:.3f} re {operator}\n")

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.raw(f"{x1:.3f} {y1:.3f} m {x2:.3f} {y2:.3f} l S\n")

    def stroke_width(self, width: float) -> None:
        self.raw(f"{width:.3f} w\n")

    def text(
        self,
        value: str,
        x: float,
        y: float,
        size: float,
        font: str = "F2",
    ) -> None:
        self.raw(f"BT /{font} {size:.3f} Tf {x:.3f} {y:.3f} Td ")
        self.parts.append(pdf_literal(value))
        self.raw(" Tj ET\n")

    def bytes(self) -> bytes:
        return b"".join(self.parts)


def pdf_literal(value: str) -> bytes:
    encoded = value.encode("cp1252", errors="replace")
    escaped = bytearray()
    for byte in encoded:
        if byte in (0x28, 0x29, 0x5C):
            escaped.extend(b"\\")
            escaped.append(byte)
        elif byte < 0x20 or byte > 0x7E:
            escaped.extend(f"\\{byte:03o}".encode("ascii"))
        else:
            escaped.append(byte)
    return b"(" + bytes(escaped) + b")"


def write_pdf(path: Path, content: bytes, width: float = A5_WIDTH_PT, height: float = A5_HEIGHT_PT) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R "
            + f"/MediaBox [0 0 {width:.3f} {height:.3f}] ".encode("ascii")
            + b"/Resources << /Font << "
            + b"/F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            + b"/Encoding /WinAnsiEncoding >> "
            + b"/F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
            + b"/Encoding /WinAnsiEncoding >> "
            + b">> >> /Contents 4 0 R >>"
        ),
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"endstream",
    ]

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(output))


def fit_grid(
    columns: int,
    rows: int,
    page_width: float = A5_WIDTH_PT,
    page_height: float = A5_HEIGHT_PT,
    margin: float = DEFAULT_MARGIN_PT,
) -> FitGrid:
    available_width = page_width - margin * 2
    available_height = page_height - margin * 2
    horizontal_strokes = (columns - 1) * STROKE_WIDTH + 2 * STROKE_WIDTH
    vertical_strokes = (rows - 1) * STROKE_WIDTH + 2 * STROKE_WIDTH
    cell = min(
        (available_width - horizontal_strokes) / columns,
        (available_height - vertical_strokes) / rows,
    )
    if cell <= 0:
        raise ValueError("Grid cannot fit within the configured page margins.")

    gap = STROKE_WIDTH
    border = STROKE_WIDTH
    width = columns * cell + (columns - 1) * gap + 2 * border
    height = rows * cell + (rows - 1) * gap + 2 * border
    return FitGrid(
        x=margin + (available_width - width) / 2,
        y=margin + (available_height - height) / 2,
        width=width,
        height=height,
        cell=cell,
        gap=gap,
        border=border,
    )


def clue_order(clue: dict) -> int:
    return 0 if clue.get("direction") == "right" else 1


@dataclass(frozen=True)
class ClueTextCapacity:
    font_size: float
    line_height: float
    text_width: float
    max_lines: int


def clue_text_capacity(cell_size: float, clue_count: int) -> ClueTextCapacity:
    segment_height = cell_size / max(clue_count, 1)
    target_lines = MIN_MULTI_CLUE_LINES if clue_count > 1 else 1
    font_size = min(
        FONT_SIZE,
        (segment_height - 2 * TEXT_PADDING_PT)
        / (target_lines * LINE_HEIGHT_RATIO),
    )
    font_size = max(MIN_FONT_SIZE, font_size)
    line_height = font_size * LINE_HEIGHT_RATIO
    arrow_x = cell_size - ARROW_MARGIN_PT - ARROW_WIDTH_PT
    text_width = max(0, arrow_x - TEXT_GAP_PT - TEXT_PADDING_PT)
    available_height = max(segment_height - 2 * TEXT_PADDING_PT, line_height)
    max_lines = max(1, math.floor(available_height / line_height))
    return ClueTextCapacity(
        font_size=font_size,
        line_height=line_height,
        text_width=text_width,
        max_lines=max_lines,
    )


def wrap_text(
    text: str,
    font_size: float,
    max_width: float,
    max_lines: int,
    clip: bool = True,
) -> list[str]:
    if max_lines <= 0 or max_width <= 0:
        return []

    words = text.split()
    lines: list[str] = []
    current = ""

    def fits(value: str) -> bool:
        return estimated_text_width(value, font_size) <= max_width

    for word in words:
        candidate = word if not current else f"{current} {word}"
        if fits(candidate):
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        if fits(word):
            current = word
        else:
            lines.extend(split_word_for_width(word, fits))
    if current:
        lines.append(current)

    if not clip or len(lines) <= max_lines:
        return lines

    clipped = lines[:max_lines]
    last = clipped[-1]
    while last and estimated_text_width(f"{last}...", font_size) > max_width:
        last = last[:-1]
    clipped[-1] = f"{last}..." if last else "..."
    return clipped


def clue_text_lines(text: str, cell_size: float, clue_count: int) -> list[str]:
    capacity = clue_text_capacity(cell_size, clue_count)
    return wrap_text(
        text,
        capacity.font_size,
        capacity.text_width,
        capacity.max_lines,
        clip=False,
    )


def clue_text_fits(text: str, cell_size: float, clue_count: int) -> bool:
    capacity = clue_text_capacity(cell_size, clue_count)
    lines = wrap_text(
        text,
        capacity.font_size,
        capacity.text_width,
        capacity.max_lines,
        clip=False,
    )
    return len(lines) <= capacity.max_lines


@lru_cache(maxsize=65536)
def clue_fits_in_grid(text: str, columns: int, rows: int, clue_count: int) -> bool:
    grid = fit_grid(columns, rows)
    return clue_text_fits(text, grid.cell, clue_count)


def unreadable_clue_issues(puzzle: dict) -> list[ClueFitIssue]:
    grid = fit_grid(int(puzzle["width"]), int(puzzle["height"]))
    issues: list[ClueFitIssue] = []

    for row_index, row in enumerate(puzzle["cells"]):
        for col_index, cell in enumerate(row):
            if cell.get("type") != "clue":
                continue

            clues = sorted(cell.get("clues", []), key=clue_order)
            capacity = clue_text_capacity(grid.cell, len(clues))
            for clue in clues:
                text = str(clue.get("text", ""))
                lines = wrap_text(
                    text,
                    capacity.font_size,
                    capacity.text_width,
                    capacity.max_lines,
                    clip=False,
                )
                if len(lines) > capacity.max_lines:
                    issues.append(
                        ClueFitIssue(
                            row=row_index,
                            col=col_index,
                            slot_id=clue.get("slotId"),
                            text=text,
                            required_lines=len(lines),
                            available_lines=capacity.max_lines,
                        )
                    )

    return issues


def format_clue_fit_issues(issues: list[ClueFitIssue]) -> str:
    return "\n".join(
        "- "
        f"{issue.slot_id or '?'}@({issue.row},{issue.col}) "
        f"needs {issue.required_lines} lines, has {issue.available_lines}: "
        f"{issue.text}"
        for issue in issues
    )


def require_readable_clues(puzzle: dict) -> None:
    issues = unreadable_clue_issues(puzzle)
    if issues:
        raise ValueError(
            "PDF clue labels cannot be displayed without truncation:\n"
            f"{format_clue_fit_issues(issues)}"
        )


def estimated_text_width(text: str, font_size: float) -> float:
    width = 0.0
    for character in text:
        if character in "ijlI.,' ":
            width += 0.28
        elif character in "mwMW":
            width += 0.78
        else:
            width += 0.55
    return width * font_size


def draw_arrow(
    canvas: PdfContent,
    x: float,
    y: float,
    width: float,
    height: float,
    clue_direction: Direction,
    answer_direction: Direction,
) -> None:
    left = x
    right = x + width
    bottom = y
    top = y + height
    mid_x = x + width * 0.5
    mid_y = y + height * 0.5
    head = min(width, height) * 0.18

    canvas.stroke_width(STROKE_WIDTH)
    if clue_direction == answer_direction == "right":
        canvas.line(left, mid_y, right, mid_y)
        canvas.line(right, mid_y, right - head, mid_y + head)
        canvas.line(right, mid_y, right - head, mid_y - head)
    elif clue_direction == answer_direction == "down":
        canvas.line(mid_x, top, mid_x, bottom)
        canvas.line(mid_x, bottom, mid_x - head, bottom + head)
        canvas.line(mid_x, bottom, mid_x + head, bottom + head)
    elif clue_direction == "right" and answer_direction == "down":
        canvas.line(left, mid_y, mid_x, mid_y)
        canvas.line(mid_x, mid_y, mid_x, bottom)
        canvas.line(mid_x, bottom, mid_x - head, bottom + head)
        canvas.line(mid_x, bottom, mid_x + head, bottom + head)
    else:
        canvas.line(mid_x, top, mid_x, mid_y)
        canvas.line(mid_x, mid_y, right, mid_y)
        canvas.line(right, mid_y, right - head, mid_y + head)
        canvas.line(right, mid_y, right - head, mid_y - head)


def draw_clue_cell(canvas: PdfContent, cell: dict, x: float, y: float, size: float) -> None:
    clues = sorted(cell.get("clues", []), key=clue_order)
    if not clues:
        return

    text_capacity = clue_text_capacity(size, len(clues))
    font_size = text_capacity.font_size
    line_height = text_capacity.line_height
    segment_height = size / len(clues)

    for index, clue in enumerate(clues):
        segment_top = y + size - index * segment_height
        segment_bottom = segment_top - segment_height
        if index > 0:
            canvas.stroke_width(STROKE_WIDTH)
            canvas.line(x, segment_top, x + size, segment_top)

        direction = clue.get("direction", "right")
        answer_direction = clue.get("answerDirection", direction)
        arrow_x = x + size - ARROW_MARGIN_PT - ARROW_WIDTH_PT
        arrow_y = segment_bottom + (segment_height - ARROW_HEIGHT_PT) / 2
        if direction == "down":
            arrow_y = segment_bottom + TEXT_PADDING_PT
        if len(clues) == 1 and direction != answer_direction:
            arrow_y = segment_bottom + ARROW_MARGIN_PT

        text_x = x + TEXT_PADDING_PT
        lines = wrap_text(
            str(clue.get("text", "")),
            font_size,
            text_capacity.text_width,
            text_capacity.max_lines,
        )
        block_height = len(lines) * line_height
        text_top = segment_bottom + (segment_height + block_height) / 2 - font_size
        if direction == "down":
            text_top = segment_top - TEXT_PADDING_PT - font_size

        for line_index, line in enumerate(lines):
            canvas.text(
                line,
                text_x,
                text_top - line_index * line_height,
                font_size,
                font="F2",
            )

        draw_arrow(
            canvas,
            arrow_x,
            arrow_y,
            ARROW_WIDTH_PT,
            ARROW_HEIGHT_PT,
            direction,
            answer_direction,
        )


def draw_puzzle(puzzle: dict) -> bytes:
    columns = int(puzzle["width"])
    rows = int(puzzle["height"])
    cells = puzzle["cells"]
    grid = fit_grid(columns, rows)
    canvas = PdfContent()

    canvas.raw("1 J 1 j\n")
    canvas.gray_fill(1)
    canvas.rect(0, 0, A5_WIDTH_PT, A5_HEIGHT_PT)
    canvas.gray_fill(0)
    canvas.gray_stroke(0)
    canvas.rect(grid.x, grid.y, grid.width, grid.height)

    for row_index, row in enumerate(cells):
        for col_index, cell in enumerate(row):
            x = grid.x + grid.border + col_index * (grid.cell + grid.gap)
            y = (
                grid.y
                + grid.height
                - grid.border
                - grid.cell
                - row_index * (grid.cell + grid.gap)
            )
            cell_type = cell.get("type")
            if cell_type == "block":
                canvas.gray_fill(BLOCK_GRAY_VALUE)
            elif cell_type == "clue":
                canvas.gray_fill(CLUE_GRAY_VALUE)
            else:
                canvas.gray_fill(1)
            canvas.rect(x, y, grid.cell, grid.cell)

    canvas.gray_stroke(0)
    canvas.gray_fill(0)
    for row_index, row in enumerate(cells):
        for col_index, cell in enumerate(row):
            if cell.get("type") != "clue":
                continue
            x = grid.x + grid.border + col_index * (grid.cell + grid.gap)
            y = (
                grid.y
                + grid.height
                - grid.border
                - grid.cell
                - row_index * (grid.cell + grid.gap)
            )
            draw_clue_cell(canvas, cell, x, y, grid.cell)

    return canvas.bytes()


def write_puzzle_pdf(puzzle: dict, path: Path) -> None:
    require_readable_clues(puzzle)
    write_pdf(path, draw_puzzle(puzzle))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a generated puzzle JSON to A5 PDF.")
    parser.add_argument("input", type=Path, help="Puzzle JSON file.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("output/pdf/puzzle.pdf"),
        help="PDF output path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    puzzle = json.loads(args.input.read_text(encoding="utf-8"))
    try:
        write_puzzle_pdf(puzzle, args.out)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
