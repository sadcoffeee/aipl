import type { Collection } from '../types'
import '../styles_lessonList.css'

//defines emoji correspinding to each lessons type
//When a lesson is shown the icon is selected based on TYPE_ICON[lesson.type]

/*
*const TYPE_ICON: Record<LessonType, string> = {
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
*/
//This defines and exports a React component named CollectionList.

export default function CollectionList({
    //props
    collections, //array of collections to display
    isAdmin,
    onOpen, //a function to call when a collection button is clicked

}: { //defining the types of the props
    collections: Collection[] 
    isAdmin: boolean
    onOpen: (lessonId: string) => void
}) {
    //return statement specififes what compoennt gives back to React
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
                
                {collections.map((collection) => ( //map goes thorugh every element in the collections array
                    <li key={collection.id}> 
                        <button
                            className="lesson-button"
                            disabled={collection.state === 'locked'}
                            onClick={() => {
                                const lessonId =
                                    collection.resumeLessonId ?? collection.lessons[0]?.id
                                {/*get recume id lesson stored in current collection ?? = use the left if not null*/}
                                if (lessonId) {
                                    onOpen(lessonId)
                                }
                            }}

                            title={
                                collection.state === 'locked'
                                    ? 'Finish the previous collection first'
                                    : undefined
                            }                        >
                            {
                                //choose which icon to display, if locked = lock
                                //aria-hidden="true" -> tell screen reader to ignore icons
                            }
                            <span className="lesson-icon" aria-hidden="true">
                                {collection.state === 'locked'
                                    ? '🔒' : '📚'} 
                                   
                            </span>

                            {
                                //display lesson title and meta data
                                //read lesson type, estimated duration, version number
                            }
                            
                            <span className="lesson-button-text">
                                {/* First row: title and estimated time */}
                                <span className="collection-heading">
                                    <span className="collection-name">
                                        {collection.title}
                                    </span>

                                    {/*display and calculate estimated time for entire collection, by adding all lessons estimated times*/}                                    
                                    <span className="collection-time">
                                        {collection.lessons.reduce(
                                            (total, lesson) => total + (lesson.estimatedMinutes ?? 0),
                                            0
                                        )} min
                                    </span>
                                </span>

                                {/* Second row: description */}
                                {collection.description && (
                                    <span className="collection-desription">
                                        {collection.description}
                                    </span>
                                )}

                                
                                {/* Third row: progress, add another class based on the collection state*/}
                                <div className={`collection-progress collection-progress--${collection.state}`}>
                                    {/*in progress icon      condition ? valueIfTrue : valueIfFalse*/}
                                    <span className="progress-icon" aria-hidden="true">
                                        {collection.state === 'completed'
                                            ? '✓'
                                            : collection.state === 'in_progress'
                                                ? '▶'
                                                : collection.state === 'locked'
                                                    ? '🚫'
                                                    : '▶'}
                                    </span>
                                    { /**/}
                                    <div className="progress-content">
                                        { /*display the compeltion count, compelted vs total*/}
                                        <span className="progress-label">
                                            {collection.progress.completed} / {collection.progress.total}
                                            {' lektioner gennemført'}
                                        </span>

                                        {/*container for progress bar*/}
                                        <div className="progress-track">
                                            <div
                                                className="progress-fill"

                                                style={{
                                                    width: `${collection.progress.total > 0 
                                                            ? (collection.progress.completed /
                                                                collection.progress.total) * 100
                                                            : 0
                                                        }%`,
                                                }}
                                            />
                                        </div>

                                       

                                    </div>
                                </div>
                            </span>

                        </button>
                    </li>
                ))}
            </ul>
        </main>
    )
}