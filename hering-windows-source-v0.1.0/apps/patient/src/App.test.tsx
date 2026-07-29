import type { QuestionSentPayload, RealtimeEnvelope } from '@hering/contracts'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { PatientWorkspace } from './PatientWorkspace'

function questionEvent(options = 3): RealtimeEnvelope {
  const payload: QuestionSentPayload = {
    question_id: 'question-1',
    field: 'severity',
    prompt: { zh: '您现在的胸闷有多严重？', en: 'How severe is your chest tightness?' },
    answer_type: 'single_choice',
    options: Array.from({ length: options }, (_, index) => ({
      code: `level-${index + 1}`,
      label: { zh: `程度 ${index + 1}`, en: `Level ${index + 1}` },
    })),
    knowledge_version: 'test',
    source_refs: ['test'],
  }
  return {
    version: '1.0',
    event_id: 'event-1',
    session_id: 'session-1',
    source_role: 'doctor',
    type: 'question.sent',
    timestamp: '2026-07-27T00:00:00.000Z',
    payload: payload as unknown as Record<string, unknown>,
  }
}

describe('patient app', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
  })

  it('renders a safe waiting state without credentials', () => {
    render(<App />)
    expect(screen.getByText('患者端')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '等待问诊会话' })).toBeInTheDocument()
  })

  it('requires an explicit confirmation before sending a structured answer', async () => {
    const sendEvent = vi.fn(() => true)
    render(
      <PatientWorkspace
        status="connected"
        sessionId="session-1"
        lastEvent={questionEvent()}
        onSendEvent={sendEvent}
      />,
    )

    fireEvent.click(await screen.findByRole('button', { name: '程度 2' }))
    expect(sendEvent).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: '确认提交' }))
    await waitFor(() => expect(sendEvent).toHaveBeenCalledWith(
      'answer.submitted',
      expect.objectContaining({
        question_id: 'question-1',
        structured_value: 'level-2',
        display_text: '程度 2',
        answer_state: 'answered',
      }),
    ))
  })

  it('paginates long option lists into touch-friendly groups of six', async () => {
    render(
      <PatientWorkspace
        status="connected"
        sessionId="session-2"
        lastEvent={questionEvent(7)}
        onSendEvent={() => true}
      />,
    )

    expect(await screen.findByRole('button', { name: '程度 6' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '程度 7' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '下一组' }))
    expect(screen.getByRole('button', { name: '程度 7' })).toBeInTheDocument()
  })
})
