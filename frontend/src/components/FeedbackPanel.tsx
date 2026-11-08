import type { Feedback } from '../types'

/** The structured feedback on an attempt. Shown as the first entry in the conversation box. */
export default function FeedbackPanel({ feedback }: { feedback: Feedback }) {
  return (
    <div className="feedback-body">
      {feedback.source === 'placeholder' && (
        <p className="badge">placeholder - ingen model forbundet</p>
      )}
      {feedback.source === 'rules' && <p className="badge">automatisk tjek</p>}

      {feedback.solved !== null && (
        <p className={feedback.solved ? 'verdict solved' : 'verdict unsolved'}>
          {feedback.solved ? 'Opgaven er løst' : 'Ikke løst endnu'}
        </p>
      )}

      <p>{feedback.summary}</p>

      {feedback.points.length > 0 && (
        <ul className="feedback-points">
          {feedback.points.map((point, index) => (
            <li key={index}>
              {point.line !== null && <span className="line-ref">linje {point.line}</span>}
              <span>{point.text}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Ids are not yet turned into titles (milestone 4), so for now this is only shown to us. */}
      {feedback.revisitLessonId && (
        <p className="revisit">
          Foreslået lektion: <code>{feedback.revisitLessonId}</code>
        </p>
      )}
    </div>
  )
}
