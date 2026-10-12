import { useState } from 'react'
import * as api from '../api'
import { Markdown } from '../markdown'
import type { ContentItem, InstructionLesson } from '../types'

function Item({ item }: { item: ContentItem }) {
  switch (item.type) {
    case 'text':
      return <Markdown source={item.markdown} />

    case 'image':
      return (
        <figure className="media">
          <img src={item.src} alt={item.alt ?? ''} />
          {item.caption && <figcaption>{item.caption}</figcaption>}
        </figure>
      )

    case 'video':
      return (
        <figure className="media">
          <video src={item.src} controls />
          {item.caption && <figcaption>{item.caption}</figcaption>}
        </figure>
      )

    case 'code':
      return (
        <figure className="media">
          <pre className="code-sample">
            <code>{item.code}</code>
          </pre>
          {item.caption && <figcaption>{item.caption}</figcaption>}
        </figure>
      )
  }
}

export default function InstructionView({
  lesson,
  onCompleted,
}: {
  lesson: InstructionLesson
  onCompleted: () => void
}) {
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  async function markRead() {
    setBusy(true)
    try {
      await api.completeLesson(lesson.id)
      setDone(true)
      onCompleted()
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="instruction">
      {lesson.content.rows.map((row, rowIndex) => (
        <div
          className={row.items.length > 1 ? 'content-row split' : 'content-row'}
          key={rowIndex}
        >
          {row.items.map((item, itemIndex) => (
            <div
              className="content-cell"
              key={itemIndex}
              style={
                row.split && row.items.length === 2
                  ? { flexGrow: row.split[itemIndex], flexBasis: 0 }
                  : undefined
              }
            >
              <Item item={item} />
            </div>
          ))}
        </div>
      ))}
      <div className="task-actions">
        <button className="primary" disabled={busy || done} onClick={() => void markRead()}>
          {done ? 'Done' : busy ? 'Saving...' : 'Continue'}
        </button>
      </div>
    </article>
  )
}
