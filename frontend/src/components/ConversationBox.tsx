import { useEffect, useRef, useState } from 'react'
import * as api from '../api'
import type { Conversation, ConversationMessage, TaskSnapshot } from '../types'
import FeedbackPanel from './FeedbackPanel'

const CONFIDENCE_LABELS: Record<number, string> = {
  1: 'Meget usikker',
  2: 'Lidt usikker',
  3: 'Hverken eller',
  4: 'Lidt sikker',
  5: 'Meget sikker',
}

/**
 * The feedback on an attempt, and the conversation that can follow it.
 */
export default function ConversationBox({
  conversation,
  lessonId,
  getSnapshot,
  onChange,
}: {
  /** null: nothing said yet in this attempt (unrestricted, before the first message). */
  conversation: Conversation | null
  lessonId: string
  /** The work so far; sent with each message while the attempt is not submitted. */
  getSnapshot?: () => TaskSnapshot
  onChange: (next: Conversation) => void
}) {
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Keep the newest message in view.
  useEffect(() => {
    const element = scrollRef.current
    if (element) element.scrollTop = element.scrollHeight
  }, [conversation?.messages.length, pending])

  async function send() {
    const text = draft.trim()
    if (!text || pending !== null) return
    setPending(text)
    setDraft('')
    setError(null)
    let current = conversation
    try {
      if (current === null) {
        current = await api.startConversation(lessonId)
        onChange(current)
      }
      const snapshot = current.submissionId === null ? getSnapshot?.() : undefined
      onChange(await api.sendChatMessage(current.id, text, snapshot))
    } catch {
      // Give the text back so nothing typed is lost, and fetch the conversation again in case it changed (closed, or out of messages) without us knowing.
      setDraft(text)
      setError('Beskeden kunne ikke sendes. Prøv igen.')
      if (current) api.fetchConversation(current.id).then(onChange).catch(() => undefined)
    } finally {
      setPending(null)
    }
  }

  const messages = conversation?.messages ?? []
  const canReply = conversation?.canReply ?? true
  const canSend = canReply && pending === null
  const hasFeedback = messages.some((message) => message.kind === 'feedback')

  return (
    <section className="conversation">
      <h2>{hasFeedback ? 'Feedback' : 'Spørg om opgaven'}</h2>

      {messages.length === 0 && pending === null && (
        <p className="muted conversation-empty">
          Du kan stille spørgsmål om opgaven når som helst, mens du arbejder.
        </p>
      )}

      <div className="conversation-messages" ref={scrollRef}>
        {messages.map((message) => (
          <MessageView key={message.id} message={message} />
        ))}
        {pending !== null && (
          <>
            <div className="message student">{pending}</div>
            <div className="message assistant typing" aria-live="polite">
              Skriver…
            </div>
          </>
        )}
      </div>

      {canReply ? (
        <div className="conversation-input">
          <textarea
            rows={2}
            value={draft}
            maxLength={1000}
            disabled={pending !== null}
            placeholder={
              hasFeedback
                ? 'Skriv et spørgsmål eller en kommentar til feedbacken…'
                : 'Skriv et spørgsmål om opgaven…'
            }
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              // Enter sends; Shift+Enter makes a new line.
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                void send()
              }
            }}
          />
          <div className="conversation-input-row">
            <span className="muted">
              {conversation &&
                `${conversation.remainingMessages} af ${conversation.maxMessages} beskeder tilbage`}
            </span>
            <button className="primary" disabled={!canSend || !draft.trim()} onClick={() => void send()}>
              Send
            </button>
          </div>
        </div>
      ) : (
        <p className="muted conversation-ended">
          {conversation?.closed
            ? 'Dette er dit seneste forsøg. Tryk på "Prøv igen" for at starte et nyt.'
            : 'Du har brugt alle beskeder til dette forsøg.'}
        </p>
      )}

      {error && <p className="conversation-error">{error}</p>}
    </section>
  )
}

function MessageView({ message }: { message: ConversationMessage }) {
  switch (message.kind) {
    case 'self_assessment':
      return (
        <div className="message student self-assessment-summary">
          <span className="muted">Din vurdering: </span>
          {message.body.confidence} – {CONFIDENCE_LABELS[message.body.confidence] ?? ''}
          {message.body.notes && <div className="notes">“{message.body.notes}”</div>}
        </div>
      )
    case 'feedback':
      return (
        <div className="message assistant feedback">
          <FeedbackPanel feedback={message.body} />
        </div>
      )
    case 'fallback':
      return <div className="message assistant fallback">{message.body.text}</div>
    default:
      return <div className={`message ${message.role}`}>{message.body.text}</div>
  }
}
