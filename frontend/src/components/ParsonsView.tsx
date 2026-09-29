import { useMemo, useState } from 'react'
import { Markdown } from '../markdown'
import type { Feedback, ParsonsLesson, ParsonsOption } from '../types'
import { useSubmissionFlow } from '../useSubmissionFlow'
import SelfAssessment from './SelfAssessment'

/** Fisher-Yates shuffle, so the option order does not give the answer away */
function shuffled<T>(items: T[]): T[] {
  const copy = [...items]
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[copy[i], copy[j]] = [copy[j], copy[i]]
  }
  return copy
}

export default function ParsonsView({
  lesson,
  onFeedback,
}: {
  lesson: ParsonsLesson
  onFeedback: (feedback: Feedback | null) => void
}) {
  const { lines, options, shuffleOptions } = lesson.content

  // useMemo keeps the shuffled order stable across re-renders; without it the options would jump around every time the student clicked something.
  const orderedOptions = useMemo(
    () => (shuffleOptions ? shuffled(options) : options),
    [lesson.id],
  )

  const slotIds = lines.flatMap((line) => (line.kind === 'slot' ? [line.id] : []))
  const [placements, setPlacements] = useState<Record<string, string | null>>(
    Object.fromEntries(slotIds.map((id) => [id, null])),
  )
  const [heldOption, setHeldOption] = useState<string | null>(null)

  const flow = useSubmissionFlow({ lessonId: lesson.id, onFeedback })
  const locked = flow.phase !== 'working'

  const usedOptionIds = new Set(Object.values(placements).filter(Boolean) as string[])
  const optionById = new Map(options.map((option) => [option.id, option]))

  function place(slotId: string, optionId: string) {
    setPlacements((current) => {
      const next = { ...current }
      // Remove the option from any box it already occupies.
      for (const key of Object.keys(next)) {
        if (next[key] === optionId) next[key] = null
      }
      next[slotId] = optionId
      return next
    })
    setHeldOption(null)
  }

  function clearSlot(slotId: string) {
    setPlacements((current) => ({ ...current, [slotId]: null }))
  }

  function onSlotClick(slotId: string) {
    if (locked) return
    if (heldOption) place(slotId, heldOption)
    else if (placements[slotId]) clearSlot(slotId)
  }

  const allFilled = slotIds.every((id) => placements[id])

  return (
    <div className="task">
      <div className="task-description">
        <Markdown source={lesson.content.description} />
      </div>

      <div className={locked ? 'parsons-code locked' : 'parsons-code'}>
        {lines.map((line, index) =>
          line.kind === 'fixed' ? (
            <pre className="parsons-line fixed" key={index}>
              <code>{line.code || ' '}</code>
            </pre>
          ) : (
            <div
              key={index}
              className={`parsons-line slot${placements[line.id] ? ' filled' : ''}`}
              style={{ paddingLeft: `${(line.indent ?? 0) * 2 + 0.5}rem` }}
              onClick={() => onSlotClick(line.id)}
              onDragOver={(event) => !locked && event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault()
                if (locked) return
                const optionId = event.dataTransfer.getData('text/plain')
                if (optionId) place(line.id, optionId)
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onSlotClick(line.id)
                }
              }}
            >
              <code>
                {placements[line.id]
                  ? optionById.get(placements[line.id]!)?.code
                  : (line.placeholder ?? 'drop a line here')}
              </code>
            </div>
          ),
        )}
      </div>

      {!locked && (
        <div className="option-bank">
          <h2>Available lines</h2>
          <p className="muted">
            Drag a line into a box, or click it and then click a box. Not all lines
            are needed.
          </p>
          <ul>
            {orderedOptions.map((option: ParsonsOption) => {
              const used = usedOptionIds.has(option.id)
              return (
                <li key={option.id}>
                  <button
                    className={`option${heldOption === option.id ? ' held' : ''}${
                      used ? ' used' : ''
                    }`}
                    draggable={!used}
                    onDragStart={(event) =>
                      event.dataTransfer.setData('text/plain', option.id)
                    }
                    onClick={() =>
                      setHeldOption(heldOption === option.id ? null : option.id)
                    }
                    disabled={used}
                  >
                    <code>{option.code}</code>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {flow.error && <div className="panel error">{flow.error}</div>}

      {flow.phase === 'working' && (
        <div className="task-actions">
          <button
            className="primary"
            disabled={flow.busy || !allFilled}
            onClick={() => flow.submitAttempt({ placements })}
          >
            {flow.busy ? 'Submitting...' : 'Submit'}
          </button>
          {!allFilled && <span className="muted">Fill every box first.</span>}
        </div>
      )}

      {flow.phase === 'assessing' && (
        <SelfAssessment busy={flow.busy} onSubmit={flow.submitAssessment} />
      )}

      {flow.phase === 'done' && (
        <div className="task-actions">
          <button onClick={flow.restart}>Try again</button>
        </div>
      )}
    </div>
  )
}
