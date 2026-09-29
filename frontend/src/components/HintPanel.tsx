
import { useEffect, useRef, useState } from 'react'
import * as api from '../api'
import { Markdown } from '../markdown'
import type { Hint, LessonHints } from '../types'

export default function HintPanel({
  hints,
  lessonId,
  highlightedId = null,
}: {
  hints: LessonHints
  lessonId: string
  highlightedId?: string | null
}) {
  const [openId, setOpenId] = useState<string | null>(null)
  const [showEarlier, setShowEarlier] = useState(false)
  const entryRefs = useRef<Record<string, HTMLLIElement | null>>({})

  // Scroll a highlighted entry into view, opening the older group if the entry is in there. Nothing sets highlightedId yet.
  useEffect(() => {
    if (!highlightedId) return
    if (hints.earlier.some((hint) => hint.id === highlightedId)) setShowEarlier(true)
    setOpenId(highlightedId)
    // Wait a tick so the group has expanded before scrolling to it.
    const timer = window.setTimeout(() => {
      entryRefs.current[highlightedId]?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
    }, 0)
    return () => window.clearTimeout(timer)
  }, [highlightedId, hints])

  function Entry({ hint }: { hint: Hint }) {
    const open = openId === hint.id
    return (
      <li
        ref={(element) => {
          entryRefs.current[hint.id] = element
        }}
        className={highlightedId === hint.id ? 'hint highlighted' : 'hint'}
      >
        <button
          className="hint-title"
          aria-expanded={open}
          onClick={() => {
            const nextId = open ? null : hint.id
            setOpenId(nextId)
            if (nextId) {
              api.logEvent({
                lessonId,
                type: 'hint_opened',
                payload: { hintId: hint.id },
              })
            }
          }}
        >
          <span className="chevron">{open ? '▾' : '▸'}</span>
          {hint.title}
        </button>
        {open && (
          <div className="hint-body">
            {hint.markdown && <Markdown source={hint.markdown} />}
            {hint.code && (
              <pre className="code-sample">
                <code>{hint.code}</code>
              </pre>
            )}
          </div>
        )}
      </li>
    )
  }

  if (hints.new.length === 0 && hints.earlier.length === 0) {
    return (
      <div className="hint-panel">
        <h2>Reference</h2>
        <p className="muted">Nothing unlocked yet.</p>
      </div>
    )
  }

  return (
    <div className="hint-panel">
      <h2>Reference</h2>

      {hints.new.length > 0 && (
        <>
          <p className="group-label">New in this lesson</p>
          <ul>
            {hints.new.map((hint) => (
              <Entry key={hint.id} hint={hint} />
            ))}
          </ul>
        </>
      )}

      {hints.earlier.length > 0 && (
        <>
          <button
            className="group-toggle"
            aria-expanded={showEarlier}
            onClick={() => setShowEarlier((value) => !value)}
          >
            <span className="chevron">{showEarlier ? '▾' : '▸'}</span>
            Earlier lessons ({hints.earlier.length})
          </button>
          {showEarlier && (
            <ul>
              {hints.earlier.map((hint) => (
                <Entry key={hint.id} hint={hint} />
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
