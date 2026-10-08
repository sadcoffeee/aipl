
export type LessonType = 'instruction' | 'completion' | 'parsons'

export type Role = 'student' | 'admin'

export interface User {
  id: string
  role: Role
  code: string | null
  username: string | null
  condition: string | null
  label: string | null
}

export interface LessonSummary {
  id: string
  order: number
  title: string
  type: LessonType
  version: number
  concepts: string[]
  estimatedMinutes: number | null
  locked: boolean
}

/** Reference library ------------------------------------------------------ */

export interface Hint {
  id: string
  title: string
  markdown?: string
  code?: string
  tags?: string[]
}

export interface LessonHints {
  /** Unlocked by this lesson. */
  new: Hint[]
  /** Unlocked earlier in the course */
  earlier: Hint[]
}

/** Instruction lessons ---------------------------------------------------- */

export interface TextItem {
  type: 'text'
  markdown: string
}

export interface MediaItem {
  type: 'image' | 'video'
  src: string
  alt?: string
  caption?: string
}

export interface CodeItem {
  type: 'code'
  language?: string
  code: string
  caption?: string
}

export type ContentItem = TextItem | MediaItem | CodeItem

export interface ContentRow {
  /* One item fills the row; two items sit side by side. */
  items: ContentItem[]
  /* Optional width weights for a two-item row, e.g. [60, 40]. */
  split?: [number, number]
}

export interface InstructionContent {
  rows: ContentRow[]
}

/** Completion lessons ----------------------------------------------------- */

export interface CompletionContent {
  description: string
  /* May contain {{gap}} markers; see gaps.ts. */
  starterCode: string
  language?: string
}

/** Parson's problems ------------------------------------------------------ */

export interface ParsonsFixedLine {
  kind: 'fixed'
  code: string
}

export interface ParsonsSlotLine {
  kind: 'slot'
  id: string
  indent?: number
  placeholder?: string
}

export type ParsonsLine = ParsonsFixedLine | ParsonsSlotLine

export interface ParsonsOption {
  id: string
  code: string
}

export interface ParsonsContent {
  description: string
  language?: string
  lines: ParsonsLine[]
  options: ParsonsOption[]
  shuffleOptions?: boolean
}

/** A full lesson ---------------------------------------------------------- */

interface LessonBase {
  id: string
  order: number
  title: string
  version: number
  contentHash: string
  concepts?: string[]
  estimatedMinutes?: number
  selfAssessment?: boolean
  /** Reference entries this lesson adds to the library. */
  unlocks?: string[]
}

export interface InstructionLesson extends LessonBase {
  type: 'instruction'
  content: InstructionContent
}

export interface CompletionLesson extends LessonBase {
  type: 'completion'
  content: CompletionContent
}

export interface ParsonsLesson extends LessonBase {
  type: 'parsons'
  content: ParsonsContent
}

export type Lesson = InstructionLesson | CompletionLesson | ParsonsLesson

/** Submission flow -------------------------------------------------------- */

export interface SubmissionResult {
  submissionId: string
  attemptNo: number
  nextStep: string
}

export interface FeedbackPoint {
  line: number | null
  text: string
  hintId?: string | null
}

export interface Feedback {
  source: 'placeholder' | 'rules' | 'llm'
  solved: boolean | null
  summary: string
  points: FeedbackPoint[]
  revisitLessonId: string | null
}

/** Admin ------------------------------------------------------------------ */

export interface ParticipantRow {
  id: string
  code: string
  condition: string | null
  label: string | null
  active: number
  created_at: string
  submission_count: number
  last_submission: string | null
}

export interface SubmissionRow {
  id: string
  lesson_id: string
  lesson_type: LessonType
  lesson_version: number | null
  attempt_no: number
  submitted_at: string
  duration_ms: number | null
  confidence: number | null
  notes: string | null
  status: string | null
  solved: number | null
}
