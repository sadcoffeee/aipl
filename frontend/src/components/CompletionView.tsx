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
  // An earlier attempt's answers, put back into the gaps when the lesson is opened again.
  // 'raw' if they no longer fit the starter code: the code is then shown as it was, without gaps.
  const [gapFill, setGapFill] = useState<string[] | 'raw' | null>(null)

  const parsed = useMemo(
    () => parseGaps(lesson.content.starterCode, Array.isArray(gapFill) ? gapFill : undefined),
    [lesson.id, lesson.content.starterCode, gapFill],
  )
  const extensions = useMemo(
    () => (gapFill === 'raw' ? [] : gapExtensions(parsed.gaps, LOCK_SCAFFOLD_OUTSIDE_GAPS)),
    [parsed, gapFill],
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

  
  const flow = useSubmissionFlow({ lessonId: lesson.id, onFeedback })

  // Show the code that was submitted, so the feedback's line numbers match what is on screen.
  useEffect(() => {
    const restored = flow.restored
    if (!restored) return
    if (restored.gapContents) {
      setGapFill(restored.gapContents)
      setCode(parseGaps(lesson.content.starterCode, restored.gapContents).text)
    } else if (restored.payload.code !== undefined) {
      setGapFill('raw')
      setCode(restored.payload.code)
    }
  }, [flow.restored, lesson.content.starterCode])

  const locked = flow.phase !== 'working'

  return (
    <div className="task">
      <div className="task-description">
        <Markdown source={lesson.content.description} />
      </div>

      <div className={locked ? 'editor-wrapper locked' : 'editor-wrapper'}>
        {/* A new key makes a new editor: its gap tracking is set up when it is created,
            so it has to start over when an earlier attempt's answers are put back. */}
        <CodeEditor
          key={gapFill === null ? 'starter' : 'restored'}
          value={code}
          onChange={setCode}
          editable={!locked}
          extensions={extensions}
        />
      </div>

     <div className="task-buttons">
        <PyRunner code={code} fileReady={fileReady} />

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
     </div>

    {flow.error && <div className="panel error">{flow.error}</div>}
      

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


