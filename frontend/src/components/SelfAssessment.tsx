import { useState } from 'react'

const OPTIONS = [
  { value: 1, label: '1 - I was guessing' },
  { value: 2, label: '2 - Mostly unsure' },
  { value: 3, label: '3 - Some idea' },
  { value: 4, label: '4 - Fairly sure' },
  { value: 5, label: '5 - I know this works' },
]

export default function SelfAssessment({
  busy,
  onSubmit,
}: {
  busy: boolean
  onSubmit: (confidence: number, notes: string) => void
}) {
  const [confidence, setConfidence] = useState<number | null>(null)
  const [notes, setNotes] = useState('')

  return (
    <section className="self-assessment">
      <h2>Before you see any feedback</h2>
      <p className="muted">
        How confident are you that your answer is correct?
      </p>

      <div className="confidence-options">
        {OPTIONS.map((option) => (
          <label key={option.value} className="confidence-option">
            <input
              type="radio"
              name="confidence"
              value={option.value}
              checked={confidence === option.value}
              onChange={() => setConfidence(option.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>

      <label className="field">
        <span>Anything you were unsure about? (optional)</span>
        <textarea
          rows={3}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="e.g. I was not sure which brackets to use"
        />
      </label>

      <button
        className="primary"
        disabled={confidence === null || busy}
        onClick={() => confidence !== null && onSubmit(confidence, notes)}
      >
        {busy ? 'Sending...' : 'Continue to feedback'}
      </button>
    </section>
  )
}
