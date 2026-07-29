import { readSessionAuth, useRealtimeSession } from '@hering/frontend-core'

import { PatientWorkspace } from './PatientWorkspace'

const apiBase = import.meta.env.VITE_API_BASE ?? ''

export function App() {
  const auth = readSessionAuth(window.location.search)
  const { status, lastEvent, sendEvent } = useRealtimeSession('patient', auth, apiBase)

  return (
    <PatientWorkspace
      status={status}
      sessionId={auth?.sessionId}
      lastEvent={lastEvent}
      onSendEvent={sendEvent}
    />
  )
}
