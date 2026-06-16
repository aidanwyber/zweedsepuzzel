# Publisher-Grade Puzzle Progress

This file tracks the work needed to make the project emit only publisher-grade
Zweedse puzzels. The word list remains CSV-based.

## Current Plan

1. Enforce publisher-grade acceptance gates in the generator.
2. Keep a draft mode for previewing templates and frontend rendering.
3. Build a dense 10x17 template catalog that can actually pass the gates.
4. Expand the CSV with enough curated Dutch entries for larger grids.
5. Add tests and export tooling once generated grids are consistently strong.

## Done

- [x] Python generator reads a CSV word list.
- [x] Generator emits JSON for the frontend.
- [x] Vite + TypeScript display renders generated puzzles.
- [x] CSV contains more than 50 Dutch word entries.
- [x] Generator supports selectable templates.
- [x] `10x17` is the default template.
- [x] Generator supports selectable quality profiles.
- [x] `publisher` profile is strict by default.
- [x] `draft` profile remains available for preview output.
- [x] Batch attempts are controlled with `--attempts`.
- [x] Quality metadata is written into generated JSON.
- [x] Frontend displays quality status and rejection reasons.
- [x] Publisher-grade mode refuses to write weak candidates.
- [x] Default 10x17 template is connected and dense enough to pass current gates.
- [x] Publisher uniqueness is clue-aware while structural uniqueness is reported.

## In Progress

- [ ] Tune publisher-grade thresholds against real reviewed examples.
- [ ] Increase CSV coverage for all template slot lengths.
- [ ] Raise interlock targets with denser templates.

## To Do

- [ ] Add at least 3 hand-authored dense 10x17 templates.
- [ ] Support clue cells with two clue arrows in one cell.
- [ ] Add grid connectivity tests.
- [ ] Add uniqueness regression tests.
- [ ] Add `IJ` normalization tests.
- [ ] Add impossible-input tests.
- [ ] Add quality-gate tests.
- [ ] Add CSV validation for duplicate answers and overlong clues.
- [ ] Add answer metadata columns while keeping CSV as the source format.
- [ ] Add clue metadata columns while keeping CSV as the source format.
- [ ] Add batch reports for rejected candidates.
- [ ] Add SVG export.
- [ ] Add PDF export.
- [ ] Add an interactive solving UI.
- [ ] Add an editor workflow for locking words and rerunning partial fills.
- [ ] Evaluate OR-Tools CP-SAT or exact-cover solving for dense templates.

## Current Blockers

- The current 10x17 template passes the first enforceable publisher profile, but
  interlock is still below the long-term editorial target.
- The CSV is large enough for the current template, but not large enough for
  reliable generation across a larger dense template catalog.
- Structural uniqueness is not guaranteed for every accepted clue-bearing
  puzzle; clue-aware uniqueness is currently the enforced publisher criterion.

## Useful Commands

Strict publisher-grade generation:

```sh
python3 -m generator.generate
```

Draft preview generation:

```sh
python3 -m generator.generate --quality draft
```

Frontend build:

```sh
cd frontend
npm run build
```
