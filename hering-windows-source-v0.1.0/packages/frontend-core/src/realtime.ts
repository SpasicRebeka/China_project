import type { RealtimeEnvelope, Role, SessionCredentials } from '@hering/contracts'
import { useCallback, useEffect, useRef, useState } from 'react'

export type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'disconnected'

export interface SessionAuth {
  sessionId: string
  token: string
}

export function readSessionAuth(search: string): SessionAuth | null {
  const params = new URLSearchParams(search)
  const sessionId = params.get('session')
  const token = params.get('token')
  return sessionId && token ? { sessionId, token } : null
}

export async function createSession(apiBase = ''): Promise<SessionCredentials> {
  const response = await fetch(`${apiBase}/api/v1/sessions`, { method: 'POST' })
  if (!response.ok) throw new Error(`Session creation failed: ${response.status}`)
  return response.json() as Promise<SessionCredentials>
}

function websocketUrl(apiBase: string, auth: SessionAuth, role: Role): string {
  const base = apiBase || window.location.origin
  const url = new URL(`/ws/v1/sessions/${auth.sessionId}`, base)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.searchParams.set('role', role)
  url.searchParams.set('token', auth.token)
  return url.toString()
}

export function useRealtimeSession(role: Role, auth: SessionAuth | null, apiBase = '') {
  const socketRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<number | undefined>(undefined)
  const sessionId = auth?.sessionId
  const token = auth?.token
  const [status, setStatus] = useState<ConnectionStatus>(auth ? 'connecting' : 'idle')
  const [lastEvent, setLastEvent] = useState<RealtimeEnvelope | null>(null)

  useEffect(() => {
    if (!sessionId || !token) {
      setStatus('idle')
      return
    }
    const connectionAuth = { sessionId, token }

    let active = true

    const connect = () => {
      if (!active) return
      setStatus('connecting')
      const socket = new WebSocket(websocketUrl(apiBase, connectionAuth, role))
      socketRef.current = socket
      socket.onopen = () => active && setStatus('connected')
      socket.onmessage = (event) => {
        if (!active) return
        setLastEvent(JSON.parse(String(event.data)) as RealtimeEnvelope)
      }
      socket.onclose = () => {
        if (!active) return
        setStatus('disconnected')
        retryRef.current = window.setTimeout(connect, 1500)
      }
      socket.onerror = () => socket.close()
    }

    connect()
    return () => {
      active = false
      if (retryRef.current !== undefined) window.clearTimeout(retryRef.current)
      socketRef.current?.close()
    }
  }, [apiBase, role, sessionId, token])

  const sendEvent = useCallback((type: string, payload: object = {}) => {
    if (!auth || socketRef.current?.readyState !== WebSocket.OPEN) return false
    const envelope: RealtimeEnvelope = {
      version: '1.0',
      event_id: crypto.randomUUID(),
      session_id: auth.sessionId,
      source_role: role,
      type,
      timestamp: new Date().toISOString(),
      payload: payload as Record<string, unknown>,
    }
    socketRef.current.send(JSON.stringify(envelope))
    return true
  }, [auth, role])

  const sendTest = useCallback(
    () => sendEvent('demo.message', { text: `connection-test:${role}` }),
    [role, sendEvent],
  )

  return { status, lastEvent, sendEvent, sendTest }
}
