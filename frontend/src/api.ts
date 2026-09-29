import type {
  Feedback,
  Lesson,
  LessonHints,
  LessonSummary,
  ParticipantRow,
  SubmissionResult,
  SubmissionRow,
  User,
} from './types'

const TOKEN_KEY = 'aipl.token'

let token: string | null = localStorage.getItem(TOKEN_KEY)

/** Called when the backend says our session is no longer valid. */
let onUnauthorized: () => void = () => undefined

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

export function setToken(value: string | null) {
  token = value
  if (value) localStorage.setItem(TOKEN_KEY, value)
  else localStorage.removeItem(TOKEN_KEY)
}

export function hasToken() {
  return token !== null
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(path, { ...options, headers })

  if (response.status === 401) {
    setToken(null)
    onUnauthorized()
    throw new ApiError(401, 'Your session has ended. Please log in again.')
  }
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (body?.detail) message = body.detail
    } catch {
      // Not JSON; the status line will have to do.
    }
    throw new ApiError(response.status, message)
  }
  return (await response.json()) as T
}

/** Authentication --------------------------------------------------------- */

export async function loginStudent(code: string): Promise<User> {
  const result = await request<{ token: string; user: User }>(
    '/api/auth/login/student',
    { method: 'POST', body: JSON.stringify({ code }) },
  )
  setToken(result.token)
  return result.user
}

export async function loginAdmin(username: string, password: string): Promise<User> {
  const result = await request<{ token: string; user: User }>('/api/auth/login/admin', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  setToken(result.token)
  return result.user
}

export function whoami(): Promise<User> {
  return request<User>('/api/auth/me')
}

export async function logout(): Promise<void> {
  try {
    await request('/api/auth/logout', { method: 'POST' })
  } finally {
    setToken(null)
  }
}

/** Content ---------------------------------------------------------------- */

export function fetchLessons(): Promise<LessonSummary[]> {
  return request<LessonSummary[]>('/api/lessons')
}

export function fetchLesson(lessonId: string): Promise<Lesson> {
  return request<Lesson>(`/api/lessons/${lessonId}`)
}

export function fetchLessonHints(lessonId: string): Promise<LessonHints> {
  return request<LessonHints>(`/api/lessons/${lessonId}/hints`)
}

/** Submissions ------------------------------------------------------------ */

export function submit(body: {
  lessonId: string
  code?: string
  placements?: Record<string, string | null>
  startedAt?: string
  durationMs?: number
}): Promise<SubmissionResult> {
  return request<SubmissionResult>('/api/submissions', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function submitSelfAssessment(
  submissionId: string,
  body: { confidence: number; notes?: string },
): Promise<Feedback> {
  return request<Feedback>(`/api/submissions/${submissionId}/self-assessment`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function fetchMySubmissions(): Promise<SubmissionRow[]> {
  return request<SubmissionRow[]>('/api/me/submissions')
}

/** Fire-and-forget logging. Failures are swallowed on purpose --------------*/
export function logEvent(body: {
  lessonId?: string
  type: string
  payload?: Record<string, unknown>
}): void {
  void request('/api/events', {
    method: 'POST',
    body: JSON.stringify(body),
  }).catch(() => undefined)
}

/** Admin ------------------------------------------------------------------ */

export function fetchParticipants(): Promise<ParticipantRow[]> {
  return request<ParticipantRow[]>('/api/admin/participants')
}

export function createParticipants(body: {
  count: number
  condition?: string | null
  label?: string | null
}): Promise<{ id: string; code: string; condition: string | null }[]> {
  return request('/api/admin/participants', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function updateParticipant(
  userId: string,
  body: { condition?: string | null; label?: string; active?: boolean },
): Promise<User> {
  return request<User>(`/api/admin/participants/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export function fetchParticipantSubmissions(userId: string): Promise<SubmissionRow[]> {
  return request<SubmissionRow[]>(`/api/admin/participants/${userId}/submissions`)
}

export function fetchExport(): Promise<unknown> {
  return request('/api/admin/export')
}
