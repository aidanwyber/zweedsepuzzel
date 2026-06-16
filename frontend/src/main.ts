import './style.css'

type Direction = 'right' | 'down'
type CellType = 'letter' | 'clue' | 'block'

interface ClueItem {
  direction: Direction
  text: string
  slotId: string
}

interface PuzzleCell {
  type: CellType
  solution?: string
  slotIds?: string[]
  clues?: ClueItem[]
}

interface PuzzleSlot {
  id: string
  direction: Direction
  answer: string
  clue: string
}

interface Puzzle {
  title: string
  algorithm: string
  width: number
  height: number
  unique: boolean
  cells: PuzzleCell[][]
  slots: PuzzleSlot[]
  metrics: {
    fillRate: number
    clueCellRatio: number
    interlockRatio: number
    letterCells: number
    clueCells: number
    slotCount: number
  }
  quality?: {
    profile: string
    passed: boolean
    score: number
    reasons: string[]
    values?: {
      structuralUnique?: boolean
      clueUnique?: boolean
    }
  }
}

const app = document.querySelector<HTMLDivElement>('#app')

if (!app) {
  throw new Error('Missing #app root')
}

const root = app
let showSolution = false

const directionLabel: Record<Direction, string> = {
  right: '>',
  down: 'v',
}

function clueOrder(direction: Direction): number {
  return direction === 'down' ? 0 : 1
}

function pct(value: number): string {
  return `${Math.round(value * 100)}%`
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => {
    const entities: Record<string, string> = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;',
    }
    return entities[char]
  })
}

function cellClass(cell: PuzzleCell): string {
  return ['cell', `cell-${cell.type}`, showSolution ? 'show-solution' : ''].join(' ')
}

function renderClues(clues: ClueItem[] = []): string {
  return [...clues]
    .sort((left, right) => clueOrder(left.direction) - clueOrder(right.direction))
    .map(
      (clue) => `
        <div class="clue-line clue-${clue.direction}">
          <span class="clue-text">${escapeHtml(clue.text)}</span>
          <span class="clue-arrow" aria-label="${clue.direction}">${directionLabel[clue.direction]}</span>
        </div>
      `,
    )
    .join('')
}

function renderGrid(puzzle: Puzzle): string {
  const rows = puzzle.cells
    .flatMap((row) =>
      row.map((cell) => {
        if (cell.type === 'clue') {
          return `<div class="${cellClass(cell)}">${renderClues(cell.clues)}</div>`
        }

        if (cell.type === 'letter') {
          return `
            <div class="${cellClass(cell)}">
              <span class="letter">${escapeHtml(cell.solution ?? '')}</span>
            </div>
          `
        }

        return `<div class="${cellClass(cell)}"></div>`
      }),
    )
    .join('')

  return `
    <section class="puzzle-board" style="--cols: ${puzzle.width}">
      ${rows}
    </section>
  `
}

function renderSlotList(slots: PuzzleSlot[]): string {
  return slots
    .map(
      (slot) => `
        <li>
          <span class="slot-direction">${directionLabel[slot.direction]}</span>
          <span>${escapeHtml(slot.clue)}</span>
          <strong>${escapeHtml(slot.answer)}</strong>
        </li>
      `,
    )
    .join('')
}

function renderQuality(puzzle: Puzzle): string {
  if (!puzzle.quality) {
    return ''
  }

  const accepted = puzzle.quality.profile === 'publisher' && puzzle.quality.passed
  const reasons = puzzle.quality.reasons.length
    ? `<ul>${puzzle.quality.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join('')}</ul>`
    : ''

  return `
    <div class="quality-panel ${accepted ? 'quality-pass' : 'quality-fail'}">
      <div>
        <span>${escapeHtml(puzzle.quality.profile)}</span>
        <strong>${accepted ? 'goedgekeurd' : 'concept'}</strong>
      </div>
      <small>score ${puzzle.quality.score}</small>
      ${reasons}
    </div>
  `
}

function render(puzzle: Puzzle): void {
  const uniquenessValue = puzzle.quality?.values?.clueUnique ?? puzzle.unique
  const uniquenessLabel = puzzle.quality?.values?.clueUnique === undefined ? 'structuur' : 'clues'

  root.innerHTML = `
    <main class="shell">
      <header class="topbar">
        <div>
          <p class="eyebrow">Zweedse puzzel</p>
          <h1>${escapeHtml(puzzle.title)}</h1>
        </div>
        <button class="solution-toggle" type="button" aria-pressed="${showSolution}">
          ${showSolution ? 'Verberg oplossing' : 'Toon oplossing'}
        </button>
      </header>

      <section class="content">
        <div class="board-wrap">
          ${renderGrid(puzzle)}
        </div>

        <aside class="side-panel">
          ${renderQuality(puzzle)}
          <div class="metrics">
            <div><span>${pct(puzzle.metrics.fillRate)}</span><small>vulling</small></div>
            <div><span>${pct(puzzle.metrics.interlockRatio)}</span><small>kruising</small></div>
            <div><span>${uniquenessValue ? 'ja' : 'nee'}</span><small>${uniquenessLabel}</small></div>
          </div>
          <ol class="slot-list">
            ${renderSlotList(puzzle.slots)}
          </ol>
        </aside>
      </section>
    </main>
  `

  document.querySelector<HTMLButtonElement>('.solution-toggle')?.addEventListener('click', () => {
    showSolution = !showSolution
    render(puzzle)
  })
}

async function loadPuzzle(): Promise<void> {
  const response = await fetch('/puzzles/puzzle.json')
  if (!response.ok) {
    throw new Error(`Could not load puzzle JSON: ${response.status}`)
  }
  render((await response.json()) as Puzzle)
}

loadPuzzle().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : 'Unknown error'
  root.innerHTML = `<main class="shell"><p class="load-error">${escapeHtml(message)}</p></main>`
})
