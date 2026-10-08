
import type { Feedback } from '../types'

export default function FeedbackPanel({ feedback }: { feedback: Feedback }) {
  return (
    <div className="feedback-panel">
      <h2>Feedback</h2>

      {feedback.source === 'placeholder' && (
        <p className="badge">placeholder - no model connected yet</p>
      )}
      {feedback.source === 'rules' && (
        <p className="badge">automatic check - written feedback comes later</p>
      )}

      {feedback.solved !== null && (
        <p className={feedback.solved ? 'verdict solved' : 'verdict unsolved'}>
          {feedback.solved ? 'Task solved' : 'Not solved yet'}
        </p>
      )}

      <p>{feedback.summary}</p>

      <ul className="feedback-points">
        {feedback.points.map((point, index) => (
          <li key={index}>
            {point.line !== null && <span className="line-ref">line {point.line}</span>}
            <span>{point.text}</span>
          </li>
        ))}
      </ul>

      {feedback.revisitLessonId && (
        <p className="revisit">
          Suggested revisit: <code>{feedback.revisitLessonId}</code>
        </p>
      )}
    </div>
  )
}
