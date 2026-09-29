import { useMemo, useState } from 'react'
import { LOCK_SCAFFOLD_OUTSIDE_GAPS } from '../config'
import { gapExtensions, parseGaps } from '../gaps'
import { Markdown } from '../markdown'
import type { CompletionLesson, Feedback } from '../types'
import { useSubmissionFlow } from '../useSubmissionFlow'
import CodeEditor from './CodeEditor'
import SelfAssessment from './SelfAssessment'

export default function CompletionView({
  lesson,
  onFeedback,
}: {
  lesson: CompletionLesson
  onFeedback: (feedback: Feedback | null) => void
}) {
  const parsed = useMemo(
    () => parseGaps(lesson.content.starterCode),
    [lesson.id, lesson.content.starterCode],
  )
  const extensions = useMemo(
    () => gapExtensions(parsed.gaps, LOCK_SCAFFOLD_OUTSIDE_GAPS),
    [parsed],
  )

  const [code, setCode] = useState(parsed.text)
  const flow = useSubmissionFlow({ lessonId: lesson.id, onFeedback })

  const locked = flow.phase !== 'working'

  return (
    <div className="task">
      <div className="task-description">
        <Markdown source={lesson.content.description} />
      </div>

      <div className={locked ? 'editor-wrapper locked' : 'editor-wrapper'}>
        <CodeEditor
          value={code}
          onChange={setCode}
          editable={!locked}
          extensions={extensions}
        />
      </div>

      {flow.error && <div className="panel error">{flow.error}</div>}

      {flow.phase === 'working' && (
        <div className="task-actions">
          <button
            className="primary"
            disabled={flow.busy}
            onClick={() => flow.submitAttempt({ code })}
          >
            {flow.busy ? 'Submitting…' : 'Submit'}
          </button>
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
