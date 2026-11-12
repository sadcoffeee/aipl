import { EditorState, StateField, Prec, type Extension } from '@codemirror/state'
import { Decoration, EditorView, WidgetType, keymap } from '@codemirror/view'

export interface Gap {
  from: number
  to: number
}

const GAP_MARKER = /\{\{gap(?::([^}]*))?\}\}/g


export function parseGaps(source: string, fill?: string[]): { text: string; gaps: Gap[] } {
  const gaps: Gap[] = []
  let text = ''
  let lastIndex = 0

  GAP_MARKER.lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = GAP_MARKER.exec(source)) !== null) {
    text += source.slice(lastIndex, match.index)
    const from = text.length
    // the earlier answer if there is one, else the author's pre-filled content, if any
    text += fill?.[gaps.length] ?? match[1] ?? ''
    gaps.push({ from, to: text.length })
    lastIndex = match.index + match[0].length
  }
  text += source.slice(lastIndex)

  return { text, gaps }
}

/** Where the gaps currently are. Every edit shifts later positions, so the stored ranges are re-mapped through each change. */
const gapField = StateField.define<Gap[]>({
  create: () => [],
  update: (gaps, tr) =>
    tr.docChanged
      ? gaps.map((gap) => ({
          from: tr.changes.mapPos(gap.from, -1),
          to: tr.changes.mapPos(gap.to, 1),
        }))
      : gaps,
})

/*Navigation function*/
// Move to the next gap when Tab is pressed
function navigateGaps(view: EditorView): boolean {
    const gaps = view.state.field(gapField)
    const cursor = view.state.selection.main.head

    // Find the next gap after the current cursor
    const nextGap = gaps.find(gap => gap.from > cursor)

    // If there is no next gap, do nothing
    if (!nextGap) return true

    // Move cursor to the next gap
    view.dispatch({
        selection: { anchor: nextGap.from },
        effects: EditorView.scrollIntoView(nextGap.from),
    })

    return true
}

/** Shown in place of an empty gap, so it is visible and clickable. */
class EmptyGapWidget extends WidgetType {
  toDOM() {
    const element = document.createElement('span')
    element.className = 'cm-gap-empty'
    element.textContent = '⌷'
    return element
  }
  ignoreEvent() {
    return false
  }
}

const gapDecorations = EditorView.decorations.compute([gapField], (state) => {
  const gaps = state.field(gapField)
  return Decoration.set(
    gaps.map((gap) =>
      gap.from === gap.to
        ? Decoration.widget({ widget: new EmptyGapWidget(), side: 1 }).range(gap.from)
        : Decoration.mark({ class: 'cm-gap' }).range(gap.from, gap.to),
    ),
    true,
  )
})

const restrictToGaps = EditorState.transactionFilter.of((tr) => {
  if (!tr.docChanged) return tr
  const gaps = tr.startState.field(gapField, false)
  if (!gaps || gaps.length === 0) return tr

  let allowed = true
  tr.changes.iterChangedRanges((fromA, toA) => {
    const inside = gaps.some((gap) => fromA >= gap.from && toA <= gap.to)
    if (!inside) allowed = false
  })
  return allowed ? tr : []
})

export function gapExtensions(gaps: Gap[], lock: boolean): Extension[] {
  if (gaps.length === 0) return []
    const base: Extension[] = [
        gapField.init(() => gaps),
        gapDecorations,
        // Give our custom Tab shortcuts the highest priority
        Prec.highest(
            keymap.of([
                {
                    key: 'Tab',
                    run: navigateGaps,
                },
            ])
        ),
    ]
  return lock ? [...base, restrictToGaps] : base
}
