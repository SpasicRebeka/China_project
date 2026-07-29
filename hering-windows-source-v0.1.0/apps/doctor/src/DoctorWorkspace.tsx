import type { ConnectionStatus } from '@hering/frontend-core'
import type {
  AnswerSubmittedPayload,
  QuestionSentPayload,
  RealtimeEnvelope,
} from '@hering/contracts'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  buildComplaintDefinitions,
  buildInterviewNodePages,
  findComplaint,
  loadKnowledgeGraph,
  systemDefinitions,
} from './graph-data'
import type {
  ComplaintDefinition,
  ComplaintId,
  InterviewNode,
  Point,
  SystemDefinition,
  SystemId,
} from './graph-data'

interface DoctorWorkspaceProps {
  apiBase?: string
  status: ConnectionStatus
  sessionId?: string
  patientUrl?: string
  error?: boolean
  lastEvent?: RealtimeEnvelope | null
  onSendEvent: (type: string, payload?: object) => boolean
}

interface PanState {
  x: number
  y: number
}

interface DragState {
  pointerId: number
  startX: number
  startY: number
  originX: number
  originY: number
}

const graphCenter: Point = { x: 292, y: 250 }

function connectionLabel(status: ConnectionStatus, error = false) {
  if (error) return '会话创建失败'
  if (status === 'connected') return '连接正常'
  if (status === 'connecting') return '正在连接'
  if (status === 'disconnected') return '连接已断开'
  return '正在创建会话'
}

function readAnswer(
  event: RealtimeEnvelope | null | undefined,
  questionId: string | null,
): AnswerSubmittedPayload | null {
  if (!event || event.type !== 'answer.submitted' || !questionId || !event.payload) return null
  const payload = event.payload
  if (
    payload.question_id !== questionId
    || typeof payload.display_text !== 'string'
    || typeof payload.answer_type !== 'string'
    || typeof payload.answer_state !== 'string'
    || typeof payload.patient_language !== 'string'
  ) {
    return null
  }
  return payload as unknown as AnswerSubmittedPayload
}

function curvedPath(from: Point, to: Point) {
  const middleX = (from.x + to.x) / 2
  const middleY = (from.y + to.y) / 2 - Math.min(22, Math.abs(from.x - to.x) * 0.08)
  return `M ${from.x} ${from.y} Q ${middleX} ${middleY} ${to.x} ${to.y}`
}

function GraphEdges({
  complaint,
  complaints,
  nodes,
  focusNodeId,
}: {
  complaint: ComplaintDefinition | null
  complaints: ComplaintDefinition[]
  nodes: InterviewNode[]
  focusNodeId: string | null
}) {
  if (complaint) {
    return (
      <svg className="graph-edges" viewBox="0 0 584 488" aria-hidden="true">
        {nodes.map((node) => (
          <path
            key={node.id}
            className={node.id === focusNodeId ? 'graph-edge graph-edge--active' : 'graph-edge'}
            d={curvedPath(graphCenter, node)}
          />
        ))}
      </svg>
    )
  }

  return (
    <svg className="graph-edges" viewBox="0 0 584 488" aria-hidden="true">
      {complaints.flatMap((item) => item.systems.map((systemId) => {
        const system = systemDefinitions.find((candidate) => candidate.id === systemId)
        if (!system) return null
        return (
          <path
            key={`${systemId}-${item.id}`}
            className="graph-edge graph-edge--overview"
            d={curvedPath(system, item)}
          />
        )
      }))}
    </svg>
  )
}

function SystemRail({
  activeSystemId,
  complaint,
  onSelect,
}: {
  activeSystemId: SystemId | null
  complaint: ComplaintDefinition | null
  onSelect: (system: SystemDefinition) => void
}) {
  return (
    <nav className="system-rail" aria-label="主诉快捷索引">
      <span className="system-rail__title">系统</span>
      <div className="system-rail__items">
        {systemDefinitions.map((system) => {
          const relatedToComplaint = complaint?.systems.includes(system.id) ?? false
          const selected = activeSystemId === system.id || relatedToComplaint
          return (
            <button
              key={system.id}
              type="button"
              className={`system-button${selected ? ' system-button--active' : ''}`}
              aria-pressed={selected}
              onClick={() => onSelect(system)}
            >
              <span className="system-button__mark" aria-hidden="true">{system.shortLabel.slice(0, 1)}</span>
              <span>{system.shortLabel}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}

export function DoctorWorkspace({
  apiBase = '',
  status,
  sessionId,
  patientUrl,
  error,
  lastEvent,
  onSendEvent,
}: DoctorWorkspaceProps) {
  const { t, i18n } = useTranslation()
  const [activeSystemId, setActiveSystemId] = useState<SystemId | null>('cardiovascular')
  const [complaintDefinitions, setComplaintDefinitions] = useState<ComplaintDefinition[]>([])
  const [knowledgeVersion, setKnowledgeVersion] = useState<string | null>(null)
  const [knowledgeStatus, setKnowledgeStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [complaintId, setComplaintId] = useState<ComplaintId | null>(null)
  const [nodePage, setNodePage] = useState(0)
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null)
  const [sentNodeId, setSentNodeId] = useState<string | null>(null)
  const [confirmedNodeIds, setConfirmedNodeIds] = useState<Set<string>>(() => new Set())
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState<PanState>({ x: 0, y: 0 })
  const [notice, setNotice] = useState('点击系统或主诉节点开始')
  const [recordOpen, setRecordOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const [copied, setCopied] = useState(false)
  const dragRef = useRef<DragState | null>(null)

  useEffect(() => {
    let active = true
    setKnowledgeStatus('loading')

    void loadKnowledgeGraph(apiBase)
      .then((database) => {
        if (!active) return
        setComplaintDefinitions(buildComplaintDefinitions(database))
        setKnowledgeVersion(database.kb_version)
        setKnowledgeStatus('ready')
        setNotice(`知识库 v${database.kb_version} 已加载`)
      })
      .catch(() => {
        if (!active) return
        setKnowledgeStatus('error')
        setNotice('知识图谱加载失败，请检查本地 API')
      })

    return () => {
      active = false
    }
  }, [apiBase])

  const complaint = findComplaint(complaintDefinitions, complaintId)
  const interviewNodePages = useMemo(
    () => complaint ? buildInterviewNodePages(complaint) : [],
    [complaint],
  )
  const interviewNodes = interviewNodePages[nodePage] ?? []
  const totalInterviewNodes = interviewNodePages.reduce((total, page) => total + page.length, 0)
  const focusNode = interviewNodes.find((node) => node.id === focusNodeId) ?? null
  const currentAnswer = readAnswer(lastEvent, sentNodeId)
  const explanationRequested = lastEvent?.type === 'explanation.requested'
    && lastEvent.payload?.question_id === sentNodeId
  const shortSessionId = sessionId?.slice(0, 8) ?? '创建中'

  const selectComplaint = (nextComplaint: ComplaintDefinition) => {
    const nextPages = buildInterviewNodePages(nextComplaint)
    setComplaintId(nextComplaint.id)
    setActiveSystemId(nextComplaint.systems[0] ?? null)
    setNodePage(0)
    setFocusNodeId(nextPages[0]?.[0]?.id ?? null)
    setSentNodeId(null)
    setConfirmedNodeIds(new Set())
    setPan({ x: 0, y: 0 })
    setZoom(1)
    setNotice(`已根据“${nextComplaint.label}”生成专属问诊图谱`)
    setDraft(`临时编号：${shortSessionId}\n知识库版本：${nextComplaint.knowledgeVersion}\n主诉：${nextComplaint.label}\n现病史：待采集`)
  }

  const resetComplaint = () => {
    setComplaintId(null)
    setNodePage(0)
    setFocusNodeId(null)
    setSentNodeId(null)
    setConfirmedNodeIds(new Set())
    setPan({ x: 0, y: 0 })
    setZoom(1)
    setNotice('请选择新的主诉，系统将重新生成图谱')
  }

  const changeNodePage = (delta: number) => {
    const nextPage = Math.min(
      interviewNodePages.length - 1,
      Math.max(0, nodePage + delta),
    )
    if (nextPage === nodePage) return
    setNodePage(nextPage)
    setFocusNodeId(interviewNodePages[nextPage]?.[0]?.id ?? null)
    setSentNodeId(null)
    setNotice(`已切换到第 ${nextPage + 1} 组问诊节点`)
  }

  const selectSystem = (system: SystemDefinition) => {
    if (complaint) {
      setNotice('当前主诉已锁定；如需更换，请先点击“重新选择”')
      return
    }
    setActiveSystemId(system.id)
    setNotice(`已聚焦${system.label}相关主诉`)
  }

  const selectInterviewNode = (node: InterviewNode) => {
    setFocusNodeId(node.id)
    setSentNodeId(null)
    setNotice(`当前焦点：${node.label}`)
  }

  const sendCurrentQuestion = () => {
    if (!focusNode) return
    const payload: QuestionSentPayload = {
      question_id: focusNode.id,
      field: focusNode.field,
      prompt: focusNode.prompt,
      answer_type: focusNode.answerType,
      options: focusNode.options,
      unit: focusNode.unit,
      knowledge_version: focusNode.knowledgeVersion,
      source_refs: focusNode.sourceRefs,
    }
    if (!onSendEvent('question.sent', payload)) {
      setNotice('患者端尚未连接，问题未发送')
      return
    }
    setSentNodeId(focusNode.id)
    setNotice(`已发送“${focusNode.label}”问题，等待患者回答`)
  }

  const confirmCurrentAnswer = () => {
    if (!focusNode || !currentAnswer) return
    if (!onSendEvent('answer.acknowledged', { question_id: focusNode.id })) {
      setNotice('连接已断开，回答尚未确认')
      return
    }
    setConfirmedNodeIds((previous) => {
      const next = new Set(previous)
      next.add(focusNode.id)
      return next
    })
    setDraft((previous) => `${previous}\n${focusNode.label}：${currentAnswer.display_text}`)
    setNotice(`已确认“${focusNode.label}”回答`)
  }

  const changeZoom = (delta: number) => {
    setZoom((current) => Math.min(1.3, Math.max(0.78, Number((current + delta).toFixed(2)))))
  }

  const resetViewport = () => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }

  const beginPan = (event: ReactPointerEvent<HTMLDivElement>) => {
    if ((event.target as HTMLElement).closest('button')) return
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: pan.x,
      originY: pan.y,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const movePan = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    setPan({
      x: Math.max(-100, Math.min(100, drag.originX + event.clientX - drag.startX)),
      y: Math.max(-80, Math.min(80, drag.originY + event.clientY - drag.startY)),
    })
  }

  const endPan = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId !== event.pointerId) return
    dragRef.current = null
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  const copyPatientLink = async () => {
    if (!patientUrl) return
    await navigator.clipboard.writeText(patientUrl)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1200)
  }

  const copyDraft = async () => {
    await navigator.clipboard.writeText(draft)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1200)
  }

  const responseState = currentAnswer
    ? `患者回答：${currentAnswer.display_text}`
    : explanationRequested
      ? '患者请求解释当前问题'
      : sentNodeId
      ? '等待患者作答'
      : '尚未发送当前问题'

  return (
    <main className="doctor-workspace">
      <span className="workspace-sr-only">{t('doctor')}</span>
      <header className="doctor-header">
        <div className="doctor-brand">
          <span className="doctor-brand__mark" aria-hidden="true">H</span>
          <div>
            <strong>{t('brand')} · 医生端</strong>
            <span>{t('subtitle')}</span>
          </div>
        </div>

        <div className="doctor-session" aria-label="会话信息">
          <span>会话 {shortSessionId}</span>
          <span className={`connection connection--${error ? 'error' : status}`}>
            <i aria-hidden="true" />
            {connectionLabel(status, error)}
          </span>
        </div>

        <div className="doctor-header__actions">
          <button type="button" className="header-button" disabled={!patientUrl} onClick={() => void copyPatientLink()}>
            {copied ? '已复制' : '患者屏幕'}
          </button>
          <label className="language-select">
            <span className="workspace-sr-only">{t('language')}</span>
            <select value={i18n.language} onChange={(event) => void i18n.changeLanguage(event.target.value)}>
              <option value="zh-CN">简中</option>
              <option value="zh-TW">繁中</option>
              <option value="en-US">EN</option>
            </select>
          </label>
        </div>
      </header>

      <div className="doctor-body">
        <section className="interview-workspace" aria-label="问诊工作区">
          <SystemRail
            activeSystemId={activeSystemId}
            complaint={complaint}
            onSelect={selectSystem}
          />

          <section className="graph-panel" aria-label={complaint ? `${complaint.label}问诊图谱` : '全局主诉图谱'}>
            <div className="graph-panel__header">
              <div>
                <span>{complaint ? '主诉专属图谱' : '全局问诊网络'}</span>
                <strong>{complaint ? `${complaint.label}问诊图谱` : '选择系统或主诉'}</strong>
                {knowledgeVersion && <small className="graph-source">知识库 v{knowledgeVersion}</small>}
              </div>
              <p aria-live="polite">{notice}</p>
              <div className="graph-toolbar" aria-label="图谱控制">
                {complaint && (
                  <button type="button" onClick={resetComplaint}>重新选择</button>
                )}
                {complaint && interviewNodePages.length > 1 && (
                  <>
                    <button
                      type="button"
                      aria-label="上一组问诊节点"
                      disabled={nodePage === 0}
                      onClick={() => changeNodePage(-1)}
                    >
                      ‹
                    </button>
                    <span className="graph-page-indicator">{nodePage + 1}/{interviewNodePages.length}</span>
                    <button
                      type="button"
                      aria-label="下一组问诊节点"
                      disabled={nodePage === interviewNodePages.length - 1}
                      onClick={() => changeNodePage(1)}
                    >
                      ›
                    </button>
                  </>
                )}
                <button type="button" aria-label="缩小图谱" onClick={() => changeZoom(-0.1)}>−</button>
                <button type="button" aria-label="图谱回到中心" onClick={resetViewport}>居中</button>
                <button type="button" aria-label="放大图谱" onClick={() => changeZoom(0.1)}>＋</button>
              </div>
            </div>

            <div
              className="graph-surface"
              onPointerDown={beginPan}
              onPointerMove={movePan}
              onPointerUp={endPan}
              onPointerCancel={endPan}
            >
              <div
                className="graph-plane"
                style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
              >
                <GraphEdges
                  complaint={complaint}
                  complaints={complaintDefinitions}
                  nodes={interviewNodes}
                  focusNodeId={focusNodeId}
                />

                {!complaint && knowledgeStatus !== 'ready' && (
                  <div className={`graph-load-state graph-load-state--${knowledgeStatus}`} role="status">
                    <strong>{knowledgeStatus === 'loading' ? '正在读取知识图谱' : '知识图谱暂不可用'}</strong>
                    <span>
                      {knowledgeStatus === 'loading'
                        ? '医疗节点将从版本化知识库生成'
                        : '请确认后端服务已启动并可访问知识库'}
                    </span>
                  </div>
                )}

                {!complaint && systemDefinitions.map((system) => (
                  <button
                    key={system.id}
                    type="button"
                    className={`network-node network-node--system${activeSystemId === system.id ? ' network-node--focus' : ''}`}
                    style={{ left: system.x, top: system.y }}
                    onClick={() => selectSystem(system)}
                  >
                    <span>{system.shortLabel}</span>
                  </button>
                ))}

                {!complaint && complaintDefinitions.map((item) => {
                  const related = activeSystemId ? item.systems.includes(activeSystemId) : true
                  return (
                    <button
                      key={item.id}
                      type="button"
                      className={`network-node network-node--complaint${related ? '' : ' network-node--dim'}`}
                      style={{ left: item.x, top: item.y }}
                      onClick={() => selectComplaint(item)}
                    >
                      <span>{item.label}</span>
                    </button>
                  )
                })}

                {complaint && (
                  <button
                    type="button"
                    className="network-node network-node--chief network-node--focus"
                    style={{ left: graphCenter.x, top: graphCenter.y }}
                    onClick={() => setFocusNodeId(null)}
                  >
                    <span>{complaint.label}</span>
                    <small>当前主诉</small>
                  </button>
                )}

                {complaint && interviewNodes.map((node) => {
                  const focused = node.id === focusNodeId
                  const confirmed = confirmedNodeIds.has(node.id)
                  return (
                    <button
                      key={node.id}
                      type="button"
                      className={`network-node network-node--question network-node--${node.kind}${focused ? ' network-node--focus' : ''}${confirmed ? ' network-node--complete' : ''}`}
                      style={{ left: node.x, top: node.y }}
                      onClick={() => selectInterviewNode(node)}
                    >
                      <span>{node.label}</span>
                      <small>{confirmed ? '已确认' : node.kind === 'associated' ? '伴随表现' : '症状属性'}</small>
                    </button>
                  )
                })}
              </div>
            </div>
          </section>
        </section>

        <aside className="clinical-sidebar">
          <section className="response-panel" aria-labelledby="response-title">
            <div className="panel-heading">
              <div>
                <span>患者端</span>
                <h2 id="response-title">实时回答</h2>
              </div>
              <span className={`mini-status mini-status--${status}`}>
                {status === 'connected' ? '患者通道正常' : connectionLabel(status, error)}
              </span>
            </div>

            <div className="current-question">
              <span>{focusNode ? focusNode.label : complaint ? '选择图谱节点' : '尚未选择主诉'}</span>
              <strong>{focusNode?.question ?? (complaint ? '点击外围节点查看并发送问题' : '从图谱中选择本次问诊主诉')}</strong>
              {focusNode && (
                <small className="question-source">
                  来源：{focusNode.sourceRefs.length > 0 ? focusNode.sourceRefs.join('、') : `知识库 v${knowledgeVersion ?? '未知'}`}
                </small>
              )}
            </div>

            <div className={`answer-state${currentAnswer || explanationRequested ? ' answer-state--ready' : ''}`}>
              <span>{responseState}</span>
              {currentAnswer && <small>{currentAnswer.answer_state === 'skipped' ? '患者跳过' : '待医生确认'}</small>}
            </div>

            <div className="response-actions">
              <button
                type="button"
                className="touch-button touch-button--secondary"
                disabled={!focusNode || status !== 'connected'}
                onClick={sendCurrentQuestion}
              >
                发送问题
              </button>
              <button
                type="button"
                className="touch-button"
                disabled={!focusNode || !currentAnswer}
                onClick={confirmCurrentAnswer}
              >
                确认回答
              </button>
            </div>
          </section>

          <section className="record-panel" aria-labelledby="record-title">
            <div className="panel-heading">
              <div>
                <span>医生可见</span>
                <h2 id="record-title">临床记录</h2>
              </div>
              <strong>{confirmedNodeIds.size} 项已确认</strong>
            </div>

            <div className="risk-summary">
              <span aria-hidden="true">!</span>
              <div>
                <strong>
                  {complaint
                    ? complaint.redFlagCount > 0
                      ? `待核对 ${complaint.redFlagCount} 项红旗规则`
                      : '知识库未配置红旗规则'
                    : '选择主诉后载入红旗规则'}
                </strong>
                <small>
                  {complaint?.redFlags[0]
                    ? `${complaint.redFlags[0].label} · ${complaint.redFlags[0].sourceRefs.join('、')}`
                    : '仅供医生人工复核，不构成诊断'}
                </small>
              </div>
            </div>

            <dl className="record-summary">
              <div><dt>临时编号</dt><dd>{shortSessionId}</dd></div>
              <div><dt>当前主诉</dt><dd>{complaint?.label ?? '未选择'}</dd></div>
              <div><dt>采集进度</dt><dd>{complaint ? `${confirmedNodeIds.size} / ${totalInterviewNodes}` : '0 / 0'}</dd></div>
            </dl>

            <div className="draft-preview">
              <span>现病史草稿</span>
              <p>{complaint ? draft.split('\n').slice(-2).join('；') : '选择主诉后生成草稿框架。'}</p>
            </div>

            <button
              type="button"
              className="touch-button touch-button--wide"
              disabled={!complaint}
              onClick={() => setRecordOpen(true)}
            >
              全屏复核草稿
            </button>
          </section>
        </aside>
      </div>

      <div className="join-panel workspace-sr-only" aria-hidden="true">
        <code>{patientUrl}</code>
      </div>
      <div className="event-readout workspace-sr-only" aria-hidden="true">
        <strong>{lastEvent?.type ?? '尚未收到消息'}</strong>
      </div>

      {recordOpen && (
        <section className="record-review" role="dialog" aria-modal="true" aria-labelledby="record-review-title">
          <header>
            <div>
              <span>现病史草稿</span>
              <h2 id="record-review-title">医生复核与编辑</h2>
            </div>
            <span>未处理提醒 0</span>
          </header>
          <textarea value={draft} onChange={(event) => setDraft(event.target.value)} aria-label="现病史草稿内容" />
          <footer>
            <button type="button" className="touch-button touch-button--secondary" onClick={() => setRecordOpen(false)}>
              返回问诊
            </button>
            <button type="button" className="touch-button" onClick={() => void copyDraft()}>
              {copied ? '已复制' : '确认并复制'}
            </button>
          </footer>
        </section>
      )}
    </main>
  )
}
