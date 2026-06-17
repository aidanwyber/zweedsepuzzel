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
- [x] Template model moved into `generator/template.py`.
- [x] Templates can be saved to and loaded from JSON.
- [x] Randomized template generator added.
- [x] Template search evaluates fill, clue ratio, interlock, connectedness, slot
      count, short slots, dual clue cells, and CSV length coverage.
- [x] Hard validation rejects readable letter runs that are not explicit slots.
- [x] Filled puzzle validation rejects readable runs that are not CSV answers.
- [x] Slot JSON supports separate answer direction and clue arrow direction.
- [x] Template search can place cross-oriented clue arrows when the entry cell
      is otherwise isolated by clue cells, block cells, or the grid edge.
- [x] Support clue cells with two clue arrows in one cell.
- [x] Template generation can stop once the requested number of passing
      templates has been found.
- [x] Template and puzzle generation defaults are stored in one shared JSON
      config file.
- [x] Template generation can run 5x5 grids for smaller search-space testing.
- [x] Template generation can require at least one valid CSP fill before saving.
- [x] Template generation can publish the best filled passing template to the
      frontend puzzle JSON.
- [x] Template generation uses heuristic beam search over partial layouts,
      guided by fill, interlock, slot progress, clue-cell economy, and length
      support.
- [x] Template generation has score-monotonic densification passes that only
      accept exact template-score improvements.
- [x] Template generation uses MRV-style pattern-domain scoring during layout
      construction.
- [x] Template generation delays expensive CSP fill checks until geometry
      candidates are ranked, then checks from best score downward.
- [x] Template generation has local repair passes that remove or replace weak
      slots on exact score improvement.
- [x] Template generation can parallelize independent geometry attempts with
      worker processes.
- [x] Template generation prunes unsupported readable runs during placement
      instead of waiting for final template evaluation.
- [x] Template generation uses cached placement masks and incremental state
      metrics for faster candidate scoring.
- [x] Puzzle filling uses bitset-backed slot domains and crossing filters.

## In Progress

- [ ] Tune publisher-grade thresholds against real reviewed examples.
- [ ] Increase CSV coverage for all template slot lengths.
- [ ] Raise interlock targets with denser templates.
- [ ] Curate saved generated templates and promote the strongest ones.
- [ ] Regenerate and verify saved templates against the readable-run constraint.

## To Do

- [ ] Add grid connectivity tests.
- [ ] Add uniqueness regression tests.
- [ ] Add `IJ` normalization tests.
- [ ] Add impossible-input tests.
- [ ] Add quality-gate tests.
- [ ] Add CSV validation for duplicate answers and overlong clues -> print any rejects.
- [ ] Add answer metadata columns while keeping CSV as the source format.
- [ ] Add clue metadata columns while keeping CSV as the source format.
- [ ] Add batch reports for rejected candidates.
- [ ] Add SVG export.
- [ ] Add PDF export.
- [ ] Add an interactive solving UI.
- [ ] Add an editor workflow for locking words and rerunning partial fills.
- [ ] Evaluate OR-Tools CP-SAT or exact-cover solving for dense templates.
- [ ] Add at least 3 hand-authored dense 10x17 templates.
- [ ] Add at least 3 generated dense 10x17 templates that pass template evaluation and puzzle generation.

## Current Blockers

- Saved 10x17 templates need regeneration and verification against the newer
  readable-run and cross-entry constraints.
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
