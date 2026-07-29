import { createSession, readSessionAuth, useRealtimeSession } from '@hering/frontend-core'
import type { SessionAuth } from '@hering/frontend-core'
import { useEffect, useRef, useState } from 'react'
import { DoctorWorkspace } from './DoctorWorkspace'

const apiBase = import.meta.env.VITE_API_BASE ?? ''

export function App() {
  const initialAuth = readSessionAuth(window.location.search)
  const [auth, setAuth] = useState<SessionAuth | null>(initialAuth)
  const [patientUrl, setPatientUrl] = useState<string>()
  const [error, setError] = useState(false)
  const started = useRef(false)
  const { status, lastEvent, sendEvent } = useRealtimeSession('doctor', auth, apiBase)

  useEffect(() => {
    if (auth || started.current) return
    started.current = true
    void createSession(apiBase)
      .then((session) => {
        setAuth({ sessionId: session.session_id, token: session.doctor_token })
        const base = import.meta.env.VITE_PATIENT_APP_URL
          ?? new URL('/patient/', window.location.origin).toString()
        const url = new URL(base)
        url.searchParams.set('session', session.session_id)
        url.searchParams.set('token', session.patient_token)
        setPatientUrl(url.toString())
      })
      .catch(() => setError(true))
  }, [auth])

  return (
    <DoctorWorkspace
      apiBase={apiBase}
      status={auth ? status : 'connecting'}
      sessionId={auth?.sessionId}
      patientUrl={patientUrl}
      error={error}
      lastEvent={lastEvent}
      onSendEvent={sendEvent}
    />
  )
}
