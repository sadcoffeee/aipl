import { useEffect, useState } from 'react'
import * as api from '../api'
import type { Feedback, Lesson, LessonHints, LessonSummary } from '../types'
import CompletionView from './CompletionView'
import FeedbackPanel from './FeedbackPanel'
import HintPanel from './HintPanel'
import InstructionView from './InstructionView'
import ParsonsView from './ParsonsView'

export default function LessonView({
  lessonId,
  lessons,
  onOpen,
  onBack,
  goalsOpen, //:
  onToggleGoals, //:
}: {
  lessonId: string
  lessons: LessonSummary[] 
  onOpen: (lessonId: string) => void
  onBack: () => void
  goalsOpen: boolean //:
  onToggleGoals: () => void //.
}) {
  const [lesson, setLesson] = useState<Lesson | null>(null)
  const [hints, setHints] = useState<LessonHints | null>(null)
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLesson(null)
    setHints(null)
    setFeedback(null)
    setError(null)
    api.fetchLesson(lessonId).then(setLesson).catch((err) => setError(String(err)))
    api.fetchLessonHints(lessonId).then(setHints).catch(() => setHints({ new: [], earlier: [] }))
  }, [lessonId])

  if (error) {
    return (
      <main className="lesson-view">
        <div className="lesson-header">
          <button className="back-button" onClick={onBack}>
            ← Back
          </button>
        </div>
        <div className="panel error">{error}</div>
      </main>
    )
  }
  if (!lesson) return <div className="panel">Loading lesson…</div>

  const hintCount = (hints?.new.length ?? 0) + (hints?.earlier.length ?? 0)
  const hasSideColumn = lesson.type !== 'instruction' || hintCount > 0

  return (
    <main className="lesson-view">
      <div className="lesson-header">
        <button className="back-button" onClick={onBack}>
          ← Back
        </button>
        <h1>{lesson.title}</h1>
      </div>

        
      <div className={['lesson-body with-goals', 
        hasSideColumn ? 'with-side' : '',
        goalsOpen ? '' : 'goals-collapsed',
      ].join(' ')}
      >
        
          <div className="goals-wrapper">
            <nav
              id='goals-navigation'
              className='goals-bar'
              hidden={!goalsOpen}
            >
            
            <details open>
              <summary className="goals-heading">
               Arbejd med EKG-data
              </summary>
              <ol className="goals-list">
                {[...lessons]
                  .sort((a,b)=> a.order - b.order)
                  .map((step, index) => (
                    <li key={step.id}>
                      <button
                        type="button"
                        className={
                          step.id === lessonId ? 'goal-step active' : 'goal-step'
                        }
                        disabled={step.locked}
                        aria-current={step.id === lessonId ? 'step' : undefined}
                        onClick={() => { 
                          if (step.id !== lessonId) onOpen(step.id)
                        }}
                    >
                        <span className="goal-number">
                          {step.locked ? '🔒' : index + 1}
                        </span>
                        
                        <span>{step.title}</span>
                      </button>
                    </li>
                ))}
               </ol>
           </details>
          </nav>

          <button
            type='button'
            className='goals-toggle'
            onClick={onToggleGoals}
          >
          <span aria-hidden="true">☰</span>
          </button>
          </div>

        <div className="lesson-main">
          {lesson.type === 'instruction' && <InstructionView lesson={lesson} />}
          {lesson.type === 'completion' && (
            <CompletionView lesson={lesson} onFeedback={setFeedback} />
          )}
          {lesson.type === 'parsons' && (
            <ParsonsView lesson={lesson} onFeedback={setFeedback} />
          )}
        </div>

        {hasSideColumn && (
          <aside className="side-column">
            {feedback ? (
              <FeedbackPanel feedback={feedback} />
            ) : (
              <HintPanel
                hints={hints ?? { new: [], earlier: [] }}
                lessonId={lesson.id}
              />
            )}
          </aside>
        )}
      </div>
    </main>
  )
}
