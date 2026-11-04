import { useState } from 'react'

const OPTIONS = [
  { value: 1, label: '1 - Meget usikker' },
  { value: 2, label: '2 - Lidt usikker' },
  { value: 3, label: '3 - Hverken eller' },
  { value: 4, label: '4 - Lidt sikker' },
  { value: 5, label: '5 - Meget sikker' },
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
      <h2>Før du modtager feedback</h2>
      <p className="muted">
        Hvor sikker er du på at dit svar er korrekt?
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
        <span>Noget du var usikker på? (valgfri)</span>
        <textarea
          rows={3}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="f.eks jeg vidste ikke hvilke paranteser jeg skulle bruge"
        />
      </label>

      <button
        className="primary"
        disabled={confidence === null || busy}
        onClick={() => confidence !== null && onSubmit(confidence, notes)}
      >
        {busy ? 'Sender...' : 'Fortsæt til feedback'}
      </button>
    </section>
  )
}
