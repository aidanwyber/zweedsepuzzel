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
- `generator/data/dutch_words.csv`: Dutch word list with short descriptions
- `generated/puzzle.json`: generated puzzle output, 10x17 by default
- `frontend/`: Vite + TypeScript display app
- `frontend/public/puzzles/puzzle.json`: puzzle JSON served by the frontend
- `deep-research-report.md`: research and algorithm notes

## Generate A Puzzle

From the repository root:

```sh
python3 -m generator.generate
```

This reads:

```text
generator/data/dutch_words.csv
```

and writes:

```text
generated/puzzle.json
frontend/public/puzzles/puzzle.json
```

The generator prints a short status line, including the selected grid and
whether the fill is unique.

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
  --seed 7
```

Available templates:

- `10x17`: default larger display grid
- `compact-6x6`: smaller smoke-test grid

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

## Build And Verify

From the repository root:

```sh
python3 -m generator.generate
python3 -m py_compile generator/generate.py
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
- right and down clue directions
- slot domains filtered by word length
- MRV slot selection
- degree and length tie-breaks
- least-constraining value ordering
- forward checking
- uniqueness check by searching for a second solution

## Current Limitations

- The 10x17 template is still an MVP layout with two clustered puzzle areas,
  not a dense publisher-grade layout.
- The frontend is a display/preview, not a full solving UI.
- There is no automated test suite yet.
- The generator is suitable for MVP-sized grids, not large production batches.

## Recommended Next Steps

1. Add a template catalog with multiple sizes and clue-cell patterns.
2. Add tests for overlap logic, impossible grids, uniqueness, and `IJ`.
3. Add scoring and batch generation across templates.
4. Add an interactive solving mode in the frontend.
5. Move larger puzzle optimization to OR-Tools CP-SAT when the word list grows.
