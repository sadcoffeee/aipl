//import two TypeScript "LessonSummary and LessonType" from a file called "types"
import type { LessonSummary, LessonType } from '../types'
import '../styles_lessonList.css'

//defines emoji correspinding to each lessons type
//When a lesson is shown the icon is selected based on TYPE_ICON[lesson.type]
const TYPE_ICON: Record<LessonType, string> = {
  instruction: '📖',
  completion: '⌨️',
  parsons: '🧩',
}

//This converts variable names into user-friendly text
//lesson.type = "completion" becomes "Completion task" on the screen
const TYPE_LABEL: Record<LessonType, string> = {
  instruction: 'Instruction',
  completion: 'Completion task',
  parsons: "Parson's problem",
}

export default function LessonList({
  //This defines and exports a React component named LessonList.
  lessons, //lessons to display 
  isAdmin, 
  onOpen, //fucntion called when lessons is clicked
}: { //what the component expects
  lessons: LessonSummary[]
  isAdmin: boolean 
  onOpen: (lessonId: string) => void
    }) {
    //builds the page layout, define what React schould render

    return (
    <main className="lesson-list">  
      <h1>Lektioner</h1> 
            <p className="muted">
                {
                //display a message for admins
                }
        {isAdmin
          ? 'Researcher view. Every lesson is available, and the reference panel shows every hint.' : ''}
      </p>
      <ul>
          {
               //generates the list of lessons
               //map goes through every item in an array and creates a value for each
               //Each lessons has a button, classname applies styling. when clicked call onOpen function and pass lesson ID
               //.locked ? display a tooltip for locked lesson
          }
        {lessons.map((lesson) => (
          <li key={lesson.id}> 
            <button
              className="lesson-button"
              disabled={lesson.locked}
              onClick={() => onOpen(lesson.id)}
              title={lesson.locked ? 'Finish the previous task first' : undefined}
           >
             {
                   //choose which icon to display, if locked = lock
                   //aria-hidden="true" -> tell screen reader to ignore icons
             }
              <span className="lesson-icon" aria-hidden="true">
                {lesson.locked ? '🔒' : TYPE_ICON[lesson.type]}
               </span>

             {
                   //display lesson title and meta data
                   //read lesson type, estimated duration, version number
             }
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
