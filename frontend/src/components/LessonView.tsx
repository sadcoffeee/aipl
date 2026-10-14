import { useCallback, useEffect, useState } from 'react'
import * as api from '../api'
import type { Feedback, Lesson, LessonHints, LessonSummary, CourseLesson } from '../types'
import CompletionView from './CompletionView'
import FeedbackPanel from './FeedbackPanel'
import HintPanel from './HintPanel'
import InstructionView from './InstructionView'
import ParsonsView from './ParsonsView'
import '../styles_goals-bar.css'

export default function LessonView({
  lessonId,
  lessons,
  onOpen,
  onBack,
  onProgressChanged,
  goalsOpen, //:
  onToggleGoals, //:
}: {
  lessonId: string
  lessons: CourseLesson[] 
  onOpen: (lessonId: string) => void
  onBack: () => void
  onProgressChanged: () => void
  goalsOpen: boolean //:
  onToggleGoals: () => void //.
}) {
  const [lesson, setLesson] = useState<Lesson | null>(null)
  const [hints, setHints] = useState<LessonHints | null>(null)
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [error, setError] = useState<string | null>(null)

  const receiveFeedback = useCallback(
    (next: Feedback | null) => {
      setFeedback(next)
      if (next) onProgressChanged()
    },
    [onProgressChanged],
  )

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
    <main className={goalsOpen ? 'lesson-view goals-open' : 'lesson-view'}>

              <div className="goals-wrapper" hidden={!goalsOpen}>
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
                  .map((step, index) => (
                    <li key={step.id}>
                      <button
                        type="button"
                        className={
                          step.id === lessonId ? 'goal-step active' : 'goal-step'
                        }
                        disabled={step.status === "locked"}
                        aria-current={step.id === lessonId ? 'step' : undefined}
                        onClick={() => { 
                          if (step.id !== lessonId) onOpen(step.id)
                        }}
                    >
                        <span className="goal-number">
                          {step.status === "locked" ? '🔒' : index + 1}
                        </span>
                        
                        <span>{step.title}</span>
                      </button>
                    </li>
                ))}
               </ol>
           </details>
          </nav>
          </div>

      <div className="lesson-header">
        
          <button
            type='button'
            className='goals-toggle'
            onClick={onToggleGoals}
          >
          <span aria-hidden="true">☰</span>
          </button>
        
        <button className="back-button" onClick={onBack}>
          ← Back
        </button>

        <h1>{lesson.title}</h1>
      </div>

        
      <div className={hasSideColumn ? 'lesson-body with-side' : 'lesson-body'}>
        

       <div className="lesson-main">
         {lesson.type === 'instruction' && (
            <InstructionView key={lesson.id} lesson={lesson} onCompleted={onProgressChanged} />
          )}
        {lesson.type === 'completion' && (
            <CompletionView key={lesson.id} lesson={lesson} onFeedback={receiveFeedback} />
          )}
          {lesson.type === 'parsons' && (
            <ParsonsView key={lesson.id} lesson={lesson} onFeedback={receiveFeedback} />
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
