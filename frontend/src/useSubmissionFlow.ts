import { useCallback, useMemo, useState } from 'react'
import * as api from './api'
import type { Feedback } from './types'

export type Phase = 'working' | 'assessing' | 'done'

export function useSubmissionFlow(args: {
  lessonId: string
  onFeedback: (feedback: Feedback | null) => void
}) {
  const { lessonId, onFeedback } = args

  const [phase, setPhase] = useState<Phase>('working')
  const [submissionId, setSubmissionId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // When the student opened this task. Recorded so time-on-task can be analysed later as it is one of the study's secondary measures
  const startedAt = useMemo(() => new Date().toISOString(), [lessonId])

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
        const feedback = await api.submitSelfAssessment(submissionId, {
          confidence,
          notes: notes.trim() || undefined,
        })
        onFeedback(feedback)
        setPhase('done')
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        setBusy(false)
      }
    },
    [submissionId, onFeedback],
  )

  /** Lets the student try again; clears the feedback column. */
  const restart = useCallback(() => {
    setPhase('working')
    setSubmissionId(null)
    onFeedback(null)
  }, [onFeedback])

  return { phase, busy, error, submitAttempt, submitAssessment, restart }
}
