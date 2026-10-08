import { useEffect, useState } from 'react'
import * as api from '../api'
import type { ParticipantRow, SubmissionRow } from '../types'

const CONDITIONS = ['intervention', 'control']

export default function AdminView() {
  const [participants, setParticipants] = useState<ParticipantRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [count, setCount] = useState(10)
  const [condition, setCondition] = useState('')
  const [label, setLabel] = useState('')
  const [justCreated, setJustCreated] = useState<string[]>([])
  const [openParticipant, setOpenParticipant] = useState<string | null>(null)
  const [submissions, setSubmissions] = useState<SubmissionRow[] | null>(null)

  function refresh() {
    api.fetchParticipants().then(setParticipants).catch((err) => setError(String(err)))
  }

  useEffect(refresh, [])

  async function create() {
    setError(null)
    try {
      const created = await api.createParticipants({
        count,
        condition: condition || null,
        label: label || null,
      })
      setJustCreated(created.map((row) => row.code))
      refresh()
    } catch (err) {
      setError(String(err))
    }
  }

  async function openSubmissions(userId: string) {
    setOpenParticipant(userId)
    setSubmissions(null)
    setSubmissions(await api.fetchParticipantSubmissions(userId))
  }

  async function downloadExport() {
    const data = await api.fetchExport()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `study-export-${new Date().toISOString().slice(0, 10)}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <main className="admin">
      <h1>Participants</h1>

      {error && <div className="panel error">{error}</div>}

      <section className="panel admin-create">
        <h2>Create codes</h2>
        <div className="admin-create-row">
          <label className="field inline">
            <span>How many</span>
            <input
              type="number"
              min={1}
              max={200}
              value={count}
              onChange={(event) => setCount(Number(event.target.value))}
            />
          </label>
          <label className="field inline">
            <span>Condition</span>
            <select
              value={condition}
              onChange={(event) => setCondition(event.target.value)}
            >
              <option value="">(unassigned)</option>
              {CONDITIONS.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="field inline grow">
            <span>Label (optional)</span>
            <input
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="e.g. pilot, 24 Sept"
            />
          </label>
          <button className="primary" onClick={() => void create()}>
            Create
          </button>
        </div>

        {justCreated.length > 0 && (
          <div className="new-codes">
            <p className="muted">
              New codes - copy these before leaving the page, they are easiest to get from here:
            </p>
            <pre className="code-sample">{justCreated.join('\n')}</pre>
          </div>
        )}
      </section>

      <div className="task-actions">
        <button onClick={() => void downloadExport()}>Download data export (JSON)</button>
        <button onClick={refresh}>Refresh</button>
      </div>

      {participants === null ? (
        <p className="muted">Loading...</p>
      ) : participants.length === 0 ? (
        <p className="muted">No participants yet. Create some codes above.</p>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Condition</th>
              <th>Label</th>
              <th>Submissions</th>
              <th>Last activity</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {participants.map((row) => (
              <tr key={row.id} className={row.active ? undefined : 'inactive'}>
                <td>
                  <code>{row.code}</code>
                </td>
                <td>
                  <select
                    value={row.condition ?? ''}
                    onChange={(event) => {
                      void api
                        .updateParticipant(row.id, {
                          condition: event.target.value || null,
                        })
                        .then(refresh)
                    }}
                  >
                    <option value="">(unassigned)</option>
                    {CONDITIONS.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </td>
                <td>{row.label ?? ''}</td>
                <td>{row.submission_count}</td>
                <td className="muted">
                  {row.last_submission ? row.last_submission.slice(0, 16).replace('T', ' ') : '—'}
                </td>
                <td>
                  <button className="link-button" onClick={() => void openSubmissions(row.id)}>
                    View
                  </button>
                  <button
                    className="link-button"
                    onClick={() => {
                      void api
                        .updateParticipant(row.id, { active: !row.active })
                        .then(refresh)
                    }}
                  >
                    {row.active ? 'Disable' : 'Enable'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {openParticipant && (
        <section className="panel">
          <div className="lesson-header">
            <h2>Submissions</h2>
            <button className="link-button" onClick={() => setOpenParticipant(null)}>
              Close
            </button>
          </div>
          {submissions === null ? (
            <p className="muted">Loading...</p>
          ) : submissions.length === 0 ? (
            <p className="muted">Nothing submitted yet.</p>
          ) : (
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Lesson</th>
                  <th>v</th>
                  <th>Attempt</th>
                  <th>Result</th>
                  <th>Confidence</th>
                  <th>Time</th>
                  <th>Submitted</th>
                </tr>
              </thead>
              <tbody>
                {submissions.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <code>{row.lesson_id}</code>
                    </td>
                    <td>{row.lesson_version ?? '-'}</td>
                    <td>{row.attempt_no}</td>
                    <td>
                      <span className={`status status-${row.status ?? 'none'}`}>
                        {row.status?.replace('_', ' ') ?? '-'}
                      </span>
                    </td>
                    <td>{row.confidence ?? '-'}</td>
                    <td>
                      {row.duration_ms ? `${Math.round(row.duration_ms / 1000)}s` : '-'}
                    </td>
                    <td className="muted">{row.submitted_at.slice(0, 16).replace('T', ' ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </main>
  )
}
