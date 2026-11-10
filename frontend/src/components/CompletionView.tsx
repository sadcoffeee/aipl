import { useMemo, useState, useEffect } from 'react'
import { LOCK_SCAFFOLD_OUTSIDE_GAPS } from '../config'
import { gapExtensions, parseGaps } from '../gaps'
import { Markdown } from '../markdown'
import type { CompletionLesson, Condition, Feedback } from '../types'
import { useSubmissionFlow } from '../useSubmissionFlow'
import CodeEditor from './CodeEditor'
import ConversationBox from './ConversationBox'
import SelfAssessment from './SelfAssessment'
import { usePy} from '../usePyodide'
import { PyRunner } from './pyRunner'



export default function CompletionView({
  lesson,
  condition,
  onFeedback,
}: {
  lesson: CompletionLesson
  condition: Condition
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

  const [fileReady, setFileReady] = useState(false)
  const { loadFile } = usePy()

useEffect(() => {
  async function prepareFile() {
    await loadFile('/datasets/EKG_data.txt', 'EKG_data.txt')
    setFileReady(true)
  }
  prepareFile()
}, [])

  
  const flow = useSubmissionFlow({ lessonId: lesson.id, condition, onFeedback })

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

      
      <PyRunner code={code} fileReady={fileReady}/>
      
      
      
      

      {flow.error && <div className="panel error">{flow.error}</div>}

      {flow.phase === 'working' && (
        <div className="task-actions">
          <button
            className="primary"
            disabled={flow.busy}
            onClick={() => flow.submitAttempt({ code })}
          >
            {flow.busy ? 'Checker svar…' : 'Check svar'}
          </button>
        </div>
      )}

      {flow.phase === 'assessing' && (
        <SelfAssessment busy={flow.busy} onSubmit={flow.submitAssessment} />
      )}

      {/* Restricted: the box appears with the feedback. Unrestricted: it is there from the
          start, and only steps aside while the self-assessment is being filled in. */}
      {((flow.phase === 'done' && flow.conversation) ||
        (flow.phase === 'working' && condition === 'unrestricted')) && (
        <ConversationBox
          conversation={flow.conversation}
          lessonId={lesson.id}
          getSnapshot={() => ({ code })}
          onChange={flow.setConversation}
        />
      )}

      {flow.phase === 'done' && (
        <div className="task-actions">
          <button onClick={flow.restart}>Prøv igen</button>
        </div>
      )}
    </div>
  )
  

}


