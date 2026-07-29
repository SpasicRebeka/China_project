import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

const knowledgeGraph = {
  kb_version: '0.1.0',
  followup_templates: {
    core_hpi_v1: {
      questions: [
        {
          id: 'core.current_status',
          field: 'current_status',
          prompt: { zh: '你现在还有这个不适吗？', en: 'Do you have this symptom right now?' },
          answer_type: 'single_choice',
          source_refs: ['S01', 'S09'],
        },
      ],
    },
  },
  symptoms: [
    {
      id: 'chest_tightness',
      label: { zh: '胸闷', en: 'Chest tightness' },
      questions: [
        {
          id: 'tightness.primary_feeling',
          field: 'primary_feeling',
          prompt: { zh: '胸闷最像哪一种感觉？', en: 'Which feeling best matches the chest tightness?' },
          answer_type: 'single_choice',
          source_refs: ['S02', 'S09'],
        },
      ],
      associated_symptoms: [
        {
          code: 'dyspnea',
          label: { zh: '气短、喘不过气', en: 'Shortness of breath' },
          source_refs: ['S02'],
        },
      ],
      red_flags: [],
    },
  ],
}

function installFetchMock() {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    if (String(input).includes('/api/v1/knowledge-graph')) {
      return Promise.resolve({
        ok: true,
        json: async () => knowledgeGraph,
      } as Response)
    }
    return new Promise(() => undefined)
  }))
}

describe('doctor app', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('renders the clinician shell while creating a session', () => {
    installFetchMock()
    render(<App />)
    expect(screen.getByText('医生端')).toBeInTheDocument()
    expect(screen.getByText('听障医疗结构化问诊终端')).toBeInTheDocument()
    expect(screen.getByText('全局问诊网络')).toBeInTheDocument()
  })

  it('regenerates a focused graph from the knowledge graph source', async () => {
    installFetchMock()
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: '胸闷' }))

    expect(screen.getByText('胸闷问诊图谱')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /主要感觉/ }))
    expect(screen.getByText('胸闷最像哪一种感觉？')).toBeInTheDocument()
    expect(screen.getByText('来源：S02、S09')).toBeInTheDocument()
  })

  it('does not fabricate medical nodes when the knowledge graph is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      if (String(input).includes('/api/v1/knowledge-graph')) {
        return Promise.resolve({ ok: false, status: 503 } as Response)
      }
      return new Promise(() => undefined)
    }))
    render(<App />)

    expect(await screen.findByText('知识图谱暂不可用')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '胸闷' })).not.toBeInTheDocument()
  })
})
