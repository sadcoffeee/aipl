import { useEffect, useRef, useState } from 'react'
import * as api from '../api'
import type { Conversation, ConversationMessage } from '../types'
import FeedbackPanel from './FeedbackPanel'

const CONFIDENCE_LABELS: Record<number, string> = {
  1: 'Meget usikker',
  2: 'Lidt usikker',
  3: 'Hverken eller',
  4: 'Lidt sikker',
  5: 'Meget sikker',
}

/**
 * The feedback on an attempt, and the short conversation that can follow it.
 *
 * Takes the place of the self-assessment box once feedback exists. The server is
 * the source of truth: every send returns the whole conversation, which replaces
 * the one shown. While waiting, the student's message is shown straight away
 * ("pending") so the box does not look frozen during the model call.
 */
export default function ConversationBox({
  conversation,
  onChange,
}: {
  conversation: Conversation
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
  }, [conversation.messages.length, pending])

  async function send() {
    const text = draft.trim()
    if (!text || pending !== null) return
    setPending(text)
    setDraft('')
    setError(null)
    try {
      onChange(await api.sendChatMessage(conversation.id, text))
    } catch {
      // Give the text back so nothing typed is lost, and fetch the conversation
      // again in case it changed (closed, or out of messages) without us knowing.
      setDraft(text)
      setError('Beskeden kunne ikke sendes. Prøv igen.')
      api.fetchConversation(conversation.id).then(onChange).catch(() => undefined)
    } finally {
      setPending(null)
    }
  }

  const canSend = conversation.canReply && pending === null

  return (
    <section className="conversation">
      <h2>Feedback</h2>

      <div className="conversation-messages" ref={scrollRef}>
        {conversation.messages.map((message) => (
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

      {conversation.canReply ? (
        <div className="conversation-input">
          <textarea
            rows={2}
            value={draft}
            maxLength={1000}
            disabled={pending !== null}
            placeholder="Skriv et spørgsmål eller en kommentar til feedbacken…"
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
              {conversation.remainingMessages} af {conversation.maxMessages} beskeder tilbage
            </span>
            <button className="primary" disabled={!canSend || !draft.trim()} onClick={() => void send()}>
              Send
            </button>
          </div>
        </div>
      ) : (
        <p className="muted conversation-ended">
          {conversation.closed
            ? 'Denne samtale er afsluttet.'
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
