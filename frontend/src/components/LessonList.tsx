import type { LessonSummary, LessonType } from '../types'

const TYPE_ICON: Record<LessonType, string> = {
  instruction: '📖',
  completion: '⌨️',
  parsons: '🧩',
}

const TYPE_LABEL: Record<LessonType, string> = {
  instruction: 'Instruction',
  completion: 'Completion task',
  parsons: "Parson's problem",
}

export default function LessonList({
  lessons,
  isAdmin,
  onOpen,
}: {
  lessons: LessonSummary[]
  isAdmin: boolean
  onOpen: (lessonId: string) => void
}) {
  return (
    <main className="lesson-list">
      <h1>Lessons</h1>
      <p className="muted">
        {isAdmin
          ? 'Researcher view. Every lesson is available, and the reference panel shows every hint.' : ''}
      </p>
      <ul>
        {lessons.map((lesson) => (
          <li key={lesson.id}>
            <button
              className="lesson-button"
              disabled={lesson.locked}
              onClick={() => onOpen(lesson.id)}
              title={lesson.locked ? 'Finish the previous task first' : undefined}
            >
              <span className="lesson-icon" aria-hidden="true">
                {lesson.locked ? '🔒' : TYPE_ICON[lesson.type]}
              </span>
              <span className="lesson-button-text">
                <span className="lesson-name">{lesson.title}</span>
                <span className="lesson-meta">
                  {TYPE_LABEL[lesson.type]}
                  {lesson.estimatedMinutes ? ` · ~${lesson.estimatedMinutes} min` : ''}
                  {isAdmin ? ` · v${lesson.version}` : ''}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </main>
  )
}
