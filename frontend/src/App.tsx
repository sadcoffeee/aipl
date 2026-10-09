/*
 * Top level of the application.
 *
 * It decides three things: is anyone logged in, are they a student or an admin, and which lesson is open. Everything else is delegated.
 *
 */

import { useCallback, useEffect, useState } from 'react'
import * as api from './api'
import AdminView from './components/AdminView'
import LessonList from './components/LessonList'
import LessonView from './components/LessonView'
import LoginView from './components/LoginView'
import type { LessonSummary, User } from './types'

type AdminTab = 'participants' | 'lessons'

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [checkingSession, setCheckingSession] = useState(true)
  const [lessons, setLessons] = useState<LessonSummary[] | null>(null)
  const [openLessonId, setOpenLessonId] = useState<string | null>(null)
  const [adminTab, setAdminTab] = useState<AdminTab>('participants')
  const [error, setError] = useState<string | null>(null)
  const [goalsOpen, setGoalsOpen] = useState(false) //.

  const signOut = useCallback(() => {
    setUser(null)
    setLessons(null)
    setOpenLessonId(null)
  }, [])

  // If the backend rejects the browser token at any point, drop back to the login screen rather than leaving a half-working session on screen.
  useEffect(() => {
    api.setUnauthorizedHandler(signOut)
  }, [signOut])

  // On load: if a token is already in localStorage, see whether it still works.
  useEffect(() => {
    async function restore() {
      if (!api.hasToken()) {
        setCheckingSession(false)
        return
      }
      try {
        setUser(await api.whoami())
      } catch {
        api.setToken(null)
      } finally {
        setCheckingSession(false)
      }
    }
    void restore()
  }, [])

  useEffect(() => {
    if (!user) return
    api
      .fetchLessons()
      .then(setLessons)
      .catch((err) => setError(String(err)))
  }, [user])

  if (checkingSession) {
    return (
      <div className="app">
        <div className="panel">Loading…</div>
      </div>
    )
  }

  if (!user) {
    return <LoginView onLoggedIn={setUser} />
  }

  const showLessons = user.role === 'student' || adminTab === 'lessons'

  return (
    <div className="app">
      <header className="app-header">
        <span className="app-title">Python for biomedical data</span>

        <div className="header-right">
          {user.role === 'admin' && openLessonId === null && (
            <nav className="tabs">
              <button
                className={adminTab === 'participants' ? 'tab active' : 'tab'}
                onClick={() => setAdminTab('participants')}
              >
                Participants
              </button>
              <button
                className={adminTab === 'lessons' ? 'tab active' : 'tab'}
                onClick={() => setAdminTab('lessons')}
              >
                Lessons
              </button>
            </nav>
          )}
          <span className="participant">
            {user.role === 'admin' ? `admin · ${user.username}` : user.code}
          </span>
          <button
            className="link-button"
            onClick={() => {
              void api.logout().finally(signOut)
            }}
          >
            Log out
          </button>
        </div>
      </header>

      {error && <div className="panel error">{error}</div>}

      {!showLessons && <AdminView />}

      {showLessons &&
        (openLessonId === null ? (
          lessons === null ? (
            <div className="panel">Loading lessons…</div>
          ) : (
            <LessonList
              lessons={lessons}
              isAdmin={user.role === 'admin'}
              onOpen={(lessonId) => { 
                api.logEvent({ lessonId, type: 'lesson_opened' })
                setOpenLessonId(lessonId)
              }}
            />
          )
        ) : (
          <LessonView
          key={openLessonId}
          lessons={lessons ?? []} //. denne og ned
          goalsOpen={goalsOpen}
          onToggleGoals={() => setGoalsOpen((open) => !open)}
          lessonId={openLessonId}
          onOpen={(lessonId)=> {
              api.logEvent({ lessonId: openLessonId, type: 'lesson_closed'})
              api.logEvent({ lessonId, type: 'lesson_opened'})
              setOpenLessonId(lessonId)
          }}
            onBack={() => {
              api.logEvent({ lessonId: openLessonId, type: 'lesson_closed' })
              setOpenLessonId(null)
              // Re-fetch so a newly unlocked lesson appears without a reload.
              api.fetchLessons().then(setLessons).catch(() => undefined)
            }}
          />
        ))}
    </div>
  )
}
