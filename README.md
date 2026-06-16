# Zweedse Puzzel MVP

This repository contains a small MVP for generating and displaying Dutch
Zweedse puzzels.

The generator is written in Python and emits puzzle JSON. The display is a
simple Vite + TypeScript page that renders the generated puzzle.

## Requirements

- Python 3.11 or newer
- Node.js and npm

The Python generator currently uses only the standard library.

## Project Layout

- `generator/generate.py`: puzzle generator
- `generator/template.py`: template model, graph utilities, and JSON storage
- `generator/template_generator.py`: randomized template search and evaluator
- `generator/templates/`: saved generated templates
- `generator/data/dutch_words.csv`: Dutch word list with short descriptions
- `generated/puzzle.json`: generated puzzle output, 10x17 by default
- `frontend/`: Vite + TypeScript display app
- `frontend/public/puzzles/puzzle.json`: puzzle JSON served by the frontend
- `deep-research-report.md`: research and algorithm notes

## Generate A Publisher-Grade Puzzle

From the repository root:

```sh
python3 -m generator.generate
```

The default quality profile is `publisher`. In this mode the generator only
writes output when a candidate passes the hard quality gates.

This reads:

```text
generator/data/dutch_words.csv
```

and writes:

```text
generated/puzzle.json
frontend/public/puzzles/puzzle.json
```

The generator prints a short status line when a candidate passes, including the
selected grid, quality profile, quality score, and structural uniqueness
diagnostic.

## Generate A Draft Preview

Use draft mode while editing templates, testing the renderer, or checking CSV
import behavior:

```sh
python3 -m generator.generate --quality draft
```

Draft mode still records quality metadata in the JSON, but it does not enforce
publisher-grade acceptance gates.

## CSV Format

The input CSV uses two columns:

```csv
answer,description
water,vloeibare stof
wind,bewegende lucht
```

Descriptions should stay short, ideally 2-3 words, because clue cells have
limited space.

Dutch `IJ` is handled as one puzzle letter internally.

The included CSV contains more than 50 Dutch entries so the 10x17 template has
enough length-matched candidates.

## Generator Options

```sh
python3 -m generator.generate --help
```

Useful options:

```sh
python3 -m generator.generate \
  --words generator/data/dutch_words.csv \
  --out generated/puzzle.json \
  --frontend-out frontend/public/puzzles/puzzle.json \
  --template 10x17 \
  --quality publisher \
  --attempts 200 \
  --seed 7
```

Available templates:

- `10x17`: default larger display grid
- `compact-6x6`: smaller smoke-test grid
- any JSON template saved in `generator/templates/`

Available quality profiles:

- `publisher`: strict mode; rejects non-unique, sparse, disconnected, or weakly
  interlocked candidates. For normal clue-bearing puzzles, uniqueness is
  clue-aware: selected clues must identify one answer in the CSV. Structural
  uniqueness is still recorded as a diagnostic.
- `draft`: preview mode; writes the best generated candidate even if it is not
  publisher-grade

## Run The Display

Install frontend dependencies once:

```sh
cd frontend
npm install
```

Start the Vite dev server:

```sh
npm run dev
```

Open the local URL printed by Vite, usually:

```text
http://127.0.0.1:5173/
```

The frontend fetches:

```text
/puzzles/puzzle.json
```

To see a newly generated puzzle, run the generator again from the repo root.
Vite will serve the updated JSON.

## Search For Templates

The randomized template generator searches candidate 10x17 layouts from the CSV
word shapes, evaluates them before solving, and stores the best passing
templates as JSON.

Basic usage:

```sh
python3 -m generator.template_generator --attempts 200 --keep 3
```

By default this reads:

```text
generator/data/dutch_words.csv
```

and writes passing templates to:

```text
generator/templates/
```

The main puzzle generator automatically loads every `*.json` template in that
directory. After a template is saved, check the available template IDs with:

```sh
python3 -m generator.generate --help
```

Then generate a puzzle from a saved template:

```sh
python3 -m generator.generate --template random-10x17-3140
```

Common options:

```sh
python3 -m generator.template_generator \
  --words generator/data/dutch_words.csv \
  --out-dir generator/templates \
  --width 10 \
  --height 17 \
  --attempts 1000 \
  --keep 5 \
  --seed 1000 \
  --max-word-length 9 \
  --clue-directions both \
  --max-clues-per-cell 2
```

Option meanings:

- `--words`: CSV source with `answer,description` columns.
- `--out-dir`: directory where passing template JSON files are saved.
- `--width` and `--height`: template grid size.
- `--attempts`: number of randomized layout candidates to try.
- `--keep`: number of top candidates to report.
- `--seed`: deterministic starting seed for reproducible searches.
- `--max-word-length`: longest CSV answer shape used while searching layouts.
- `--clue-directions`: allowed clue arrows: `right`, `down`, or `both`.
  Answers always read horizontally right or vertically down.
- `--max-clues-per-cell`: `1` or `2`. With `2`, a clue cell can contain one
  right-arrow clue and one down-arrow clue, but never overlapping arrows.
- `--save-rejected`: also save rejected top candidates for inspection.
- `--verbose`: print passing attempts as they are found.

The search keeps passing and rejected candidates in separate leaderboards.
Passing templates are always reported first and saved. Rejected templates are
reported as near-misses, even when they score higher than passing templates.

By default, rejected candidates are printed but not saved. To save them for
inspection:

```sh
python3 -m generator.template_generator --attempts 50 --save-rejected
```

To see passing templates as they are found:

```sh
python3 -m generator.template_generator --attempts 20 --seed 100001 --verbose
```

The template generator does not fill the final puzzle with answers. It uses CSV
word shapes to search plausible slot geometry, then the main generator performs
the actual CSP fill against the chosen template.

Template slots store both:

- `direction`: the answer reading direction, either `right` or `down`.
- `clueDirection`: the arrow direction from the clue cell to the first answer
  cell, either `right` or `down`.

Usually these are the same. The template generator may also place a vertical
answer whose clue arrow points right, or a horizontal answer whose clue arrow
points down, when the first answer cell is otherwise surrounded by clue cells,
block cells, or the grid edge. Existing templates without `clueDirection` still
load as same-direction clue slots.

Template evaluation follows the research report's template-first approach:

- fill rate
- clue-cell ratio
- interlock ratio
- connected slot graph
- slot count
- short-slot ratio
- dual-clue-cell use
- word-length coverage from the CSV
- hard word termination: the cell after a slot must be grid edge, clue cell, or
  block, never another letter cell
- hard readable-run validation: every contiguous horizontal or vertical run of
  at least 3 letters must be an explicit slot, and every such filled run must
  be an answer from the CSV

Recommended workflow:

1. Search templates:

```sh
python3 -m generator.template_generator --attempts 1000 --keep 5
```

2. Pick a saved template ID from `generator/templates/`.

3. Generate and validate a puzzle from that template:

```sh
python3 -m generator.generate --template <template-id> --attempts 200
```

4. Preview it in the frontend:

```sh
cd frontend
npm run dev
```

## Build And Verify

From the repository root:

```sh
python3 -m generator.generate --quality draft
python3 -m py_compile generator/generate.py
python3 -m py_compile generator/template.py generator/template_generator.py
```

From `frontend/`:

```sh
npm run build
```

## Algorithm

The MVP follows the recommendation in `deep-research-report.md`: a
template-driven crossword-style CSP solver.

Current implementation:

- selectable Swedish-style templates, with `10x17` as the default
- strict `publisher` quality profile
- permissive `draft` preview profile
- batch candidate generation via `--attempts`
- connected dense 10x17 default template
- template JSON load/save through `Template`
- randomized template search and pre-solve evaluation
- hard template constraint preventing words from visually continuing past their
  final cell
- right and down clue directions
- slot domains filtered by word length
- MRV slot selection
- degree and length tie-breaks
- least-constraining value ordering
- forward checking
- structural uniqueness check by searching for a second solution
- clue-aware uniqueness check against the CSV
- quality gates for uniqueness, connectedness, fill rate, interlock ratio, slot
  count, short-word ratio, and clue length

## Current Limitations

- The 10x17 template is connected and passes the current publisher profile, but
  the interlock threshold is still lower than the long-term target for dense
  editorial puzzles.
- The frontend is a display/preview, not a full solving UI.
- There is no automated test suite yet.
- The generator is suitable for MVP-sized grids, not large production batches.

## Recommended Next Steps

1. Add a template catalog with multiple sizes and clue-cell patterns.
2. Add tests for overlap logic, impossible grids, uniqueness, and `IJ`.
3. Add scoring and batch generation across templates.
4. Add an interactive solving mode in the frontend.
5. Move larger puzzle optimization to OR-Tools CP-SAT when the word list grows.
