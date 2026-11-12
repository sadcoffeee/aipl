import { useCallback, useEffect, useState } from 'react'
import * as api from './api'
import type { Conversation, Feedback, RestoredSubmission } from './types'

/** loading: asking the server what to show; no buttons until it answers. */
export type Phase = 'loading' | 'working' | 'assessing' | 'done'

export function useSubmissionFlow(args: {
  lessonId: string
  onFeedback: (feedback: Feedback | null) => void
}) {
  const { lessonId, onFeedback } = args

  const [phase, setPhase] = useState<Phase>('loading')
  const [submissionId, setSubmissionId] = useState<string | null>(null)
  // The feedback and the replies after it. Shown in place of the self-assessment once it exists.
  const [conversation, setConversation] = useState<Conversation | null>(null)

  // An earlier attempt loaded when the task opened; the views put its code or placements back.
  const [restored, setRestored] = useState<RestoredSubmission | null>(null)

  // When the task opens, carry on where the student left off: a chat in progress (unrestricted), an ungiven self-assessment, or the latest attempt and its feedback.
  useEffect(() => {
    let cancelled = false
    api
      .resumeLesson(lessonId)
      .then((resume) => {
        if (cancelled) return
        if (resume.submission) {
          setRestored(resume.submission)
          setSubmissionId(resume.submission.id)
        }
        setConversation(resume.conversation)
        setPhase(
          resume.state === 'assessing' ? 'assessing' : resume.state === 'reviewing' ? 'done' : 'working',
        )
      })
      .catch(() => {
        if (!cancelled) setPhase('working')
      })
    return () => {
      cancelled = true
    }
  }, [lessonId])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // When the student opened this task. Recorded so time-on-task can be analysed later as it is one of the study's secondary measures
  // Reset by restart, so a new attempt is not timed from when the lesson was opened.
  const [startedAt, setStartedAt] = useState(() => new Date().toISOString())

  const submitAttempt = useCallback(
    async (payload: { code?: string; placements?: Record<string, string | null> }) => {
      setBusy(true)
      setError(null)
      try {
        const result = await api.submit({
          lessonId,
          startedAt,
          durationMs: Date.now() - new Date(startedAt).getTime(),
          ...payload,
        })
        setSubmissionId(result.submissionId)
        setPhase('assessing')
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        setBusy(false)
      }
    },
    [lessonId, startedAt],
  )

  const submitAssessment = useCallback(
    async (confidence: number, notes: string) => {
      if (!submissionId) return
      setBusy(true)
      setError(null)
      try {
        const result = await api.submitSelfAssessment(submissionId, {
          confidence,
          notes: notes.trim() || undefined,
        })
        setConversation(result.conversation)
        onFeedback(result)
        setPhase('done')
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        setBusy(false)
      }
    },
    [submissionId, onFeedback],
  )

  /** Lets the student try again. The old conversation stays on the server, closed once the next attempt is assessed. */
  const restart = useCallback(() => {
    setPhase('working')
    setSubmissionId(null)
    setConversation(null)
    setStartedAt(new Date().toISOString())
    onFeedback(null)
  }, [onFeedback])

  return {
    phase,
    busy,
    error,
    conversation,
    setConversation,
    restored,
    submitAttempt,
    submitAssessment,
    restart,
  }
}
