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
- `generator/config.json`: shared generation and template-search settings
- `generator/templates/`: saved generated templates
- `generator/data/peter_words.csv`: configured word list with short descriptions
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
generator/data/peter_words.csv
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

The input CSV uses two columns. A header is optional:

```csv
answer,description
water,vloeibare stof
wind,bewegende lucht
```

Headerless CSV files are also accepted:

```csv
water,vloeibare stof
wind,bewegende lucht
```

Descriptions should stay short, ideally 2-3 words, because clue cells have
limited space.

Dutch `IJ` is handled as one puzzle letter internally.

The active CSV path is configured once in `generator/config.json` with the
top-level `words` setting.

## Generator Options

```sh
python3 -m generator.generate --help
```

Useful options:

```sh
python3 -m generator.generate \
  --config generator/config.json \
  --words generator/data/peter_words.csv \
  --out generated/puzzle.json \
  --frontend-out frontend/public/puzzles/puzzle.json \
  --emit-pdf \
  --pdf-out output/pdf/puzzle.pdf \
  --name-by-template \
  --template 10x17 \
  --quality publisher \
  --attempts 200 \
  --seed 7
```

Every option above has a default in `generator/config.json`. Command line flags
override the config file.

Set `--seed -1` to choose a random seed between `10000` and `10000000` for that
run. The resolved seed is printed and recorded in generated puzzle metadata.

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

The randomized template generator searches candidate layouts from the CSV word
shapes, evaluates them before solving, and stores the best passing templates as
JSON.

Basic usage:

```sh
python3 -m generator.template_generator --attempts 200 --keep 3
```

By default, `generator/config.json` is used. Its `templateSearch` section
defines the default search size, heuristic weights, and template evaluation
thresholds. CLI flags override those values. Use `--width 5 --height 5` when
you want a smaller search space for quick experiments, and `--width 10 --height
17` for production-sized templates.

By default this reads:

```text
generator/data/peter_words.csv
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

For saved 5x5 test templates, use draft quality if you call the main generator
directly:

```sh
python3 -m generator.generate --template random-5x5-1010 --quality draft
```

The default `publisher` profile is sized for larger grids and will reject 5x5
test templates for having too few slots.

Common options:

```sh
python3 -m generator.template_generator \
  --config generator/config.json \
  --words generator/data/peter_words.csv \
  --out-dir generator/templates \
  --width 5 \
  --height 5 \
  --attempts 120 \
  --keep 5 \
  --seed 1000 \
  --max-word-length 9 \
  --clue-directions both \
  --max-clues-per-cell 2
```

Option meanings:

- `--words`: CSV source with two columns, with or without an
  `answer,description` header.
- `--out-dir`: directory where passing template JSON files are saved.
- `--width` and `--height`: template grid size.
- `--attempts`: number of randomized layout candidates to try.
- `--keep`: number of top candidates to report.
- `--seed`: deterministic starting seed for reproducible searches. Use `-1` to
  choose a random seed between `10000` and `10000000` for that run.
- `--max-word-length`: longest CSV answer shape used while searching layouts.
- `--clue-directions`: allowed clue arrows: `right`, `down`, or `both`.
  Answers always read horizontally right or vertically down.
- `--max-clues-per-cell`: `1` or `2`. With `2`, a clue cell can contain one
  right-arrow clue and one down-arrow clue, but never overlapping arrows.
- `--save-rejected`: also save rejected top candidates for inspection.
- `--verbose`: print passing attempts as they are found.
- `--stop-when-enough-passing` / `--no-stop-when-enough-passing`: stop after
  `--keep` passing templates have been found, or keep searching for better
  scores until `--attempts` is exhausted. When disabled, all passing templates
  are ranked after the full run and only the best `--keep` are saved.
- `--require-fill` / `--no-require-fill`: only accept templates that can also
  generate at least one valid filled puzzle.
- `--fill-attempts` and `--fill-seed`: control the CSP fill check used by
  `--require-fill`. Use `--fill-seed -1` to choose a random fill seed for that
  run.
- `--emit-puzzle` / `--no-emit-puzzle`: write the best filled passing template
  to `generated/puzzle.json` and `frontend/public/puzzles/puzzle.json`.
- `--puzzle-out` and `--frontend-out`: output paths used by `--emit-puzzle`.
- `--emit-pdf` / `--no-emit-pdf`: when `--emit-puzzle` writes the best filled
  passing puzzle, also render it as an A5 grayscale PDF.
- `--pdf-out`: output path used by `--emit-puzzle --emit-pdf`.
- `--name-by-template` / `--no-name-by-template`: append the template id to PDF
  filenames, for example `puzzle-10x17.pdf`.
- `--beam-width`: number of partial template states kept during construction.
- `--branching-factor`: number of candidate placements expanded from each beam
  state.
- `--placement-steps`: maximum word-placement steps per template attempt.
- `--candidate-pool`: number of high-scoring candidate placements considered
  before beam expansion.
- `--randomness`: small score jitter used to diversify repeated attempts.
- `--densify-passes`: post-construction passes that try adding legal placements
  and accept only exact `evaluate_template` score improvements.
- `--densify-candidate-pool`: number of ranked placements checked per
  densification pass.
- `--densify-min-gain`: minimum exact score increase needed to accept a
  densification move.
- `--repair-passes`: local mutation passes that remove or replace weak slots
  only when the exact template score improves.
- `--repair-candidate-pool`: number of removals/replacements checked per repair
  pass.
- `--repair-min-gain`: minimum exact score increase needed to accept a repair
  move.
- `--workers`: number of worker processes for independent geometry attempts.

The search keeps passing and rejected candidates in separate leaderboards.
Passing templates are always reported first and saved. Rejected templates are
reported as near-misses, even when they score higher than passing templates.
If you press `Ctrl-C`, the current attempt is abandoned but previously collected
passing and rejected candidates are still ranked, saved, and published according
to the same options.

By default, rejected candidates are printed but not saved. To save them for
inspection:

```sh
python3 -m generator.template_generator --attempts 50 --save-rejected
```

To see passing templates as they are found:

```sh
python3 -m generator.template_generator --attempts 20 --seed 100001 --verbose
```

The search is geometry-first. It uses CSV word shapes to find plausible slot
layouts, ranks geometrically passing candidates, and then, when `--require-fill`
is enabled, calls the main CSP generator from the best geometry score downward
until enough fillable templates have been found. With `--emit-puzzle`, the best
filled passing template is also written to the normal generated puzzle outputs.
During template construction, placements that would create unsupported readable
runs of two or more letters are pruned before entering the beam. A partial run
is allowed only when it is already a CSV answer or can still be extended into
one within the available open cells.

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
  at least 2 letters must be an explicit slot, and every such filled run must
  be an answer from the CSV

Recommended workflow:

1. Search templates:

```sh
python3 -m generator.template_generator --attempts 120 --keep 5
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
python3 -m py_compile generator/config.py generator/generate.py
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
- heuristic beam search for template construction, scored on projected fill,
  interlock, slot progress, clue-cell economy, and word-length support
- pattern-domain scoring that estimates how many CSV words can fit known slot
  letters during template construction
- early readable-run pruning that rejects placements creating unsupported
  two-letter-or-longer fragments before scoring
- cached placement cell masks and incremental state metrics for fill,
  interlock, and short-slot scoring
- delayed fillability checks: geometry candidates are ranked first, then the
  CSP fill check runs from the best-scoring geometry downward until enough
  fillable templates are found
- optional local repair passes that remove or replace weak slots on exact score
  improvement
- optional multiprocessing over independent geometry attempts
- bitset-backed CSP fill domains and crossing filters
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
