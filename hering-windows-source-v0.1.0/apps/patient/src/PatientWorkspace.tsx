import type {
  AnswerSubmittedPayload,
  ClinicalAnswerOption,
  QuestionSentPayload,
  RealtimeEnvelope,
  SupportedPatientLocale,
} from '@hering/contracts'
import type { ConnectionStatus } from '@hering/frontend-core'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

interface PatientWorkspaceProps {
  status: ConnectionStatus
  sessionId?: string
  lastEvent?: RealtimeEnvelope | null
  onSendEvent: (type: string, payload?: object) => boolean
}

type SubmissionState = 'draft' | 'submitting' | 'submitted'

interface AnswerDraft {
  question: QuestionSentPayload | null
  selectedCodes: string[]
  inputValue: string
  durationUnit: string
  submissionState: SubmissionState
  submittedText: string
  acknowledged: boolean
}

interface PatientCopy {
  patient: string
  session: string
  missingTitle: string
  missingHint: string
  connectingTitle: string
  connectingHint: string
  waitingTitle: string
  waitingHint: string
  disconnectedTitle: string
  disconnectedHint: string
  endedTitle: string
  endedHint: string
  questionLabel: string
  singleHint: string
  multiHint: string
  numberHint: string
  dateHint: string
  durationHint: string
  textHint: string
  textFallback: string
  askToRecord: string
  submit: string
  submitting: string
  explain: string
  explainSent: string
  skip: string
  skipConfirmTitle: string
  skipConfirmHint: string
  cancel: string
  confirmSkip: string
  sentTitle: string
  sentHint: string
  acknowledged: string
  correction: string
  correctionSent: string
  sendFailed: string
  noOptions: string
  previousGroup: string
  nextGroup: string
  groupStatus: (current: number, total: number) => string
  selectedCount: (count: number) => string
  privacy: string
  minutes: string
  hours: string
  days: string
  weeks: string
  deleteDigit: string
}

const copyByLocale: Record<SupportedPatientLocale, PatientCopy> = {
  'zh-CN': {
    patient: '患者端',
    session: '会话',
    missingTitle: '等待问诊会话',
    missingHint: '请使用医生端生成的患者链接进入本次问诊。',
    connectingTitle: '正在连接医生端',
    connectingHint: '请稍候，不需要进行其他操作。',
    waitingTitle: '已连接，请等待医生提问',
    waitingHint: '医生发送问题后，本屏会自动显示。',
    disconnectedTitle: '连接已断开',
    disconnectedHint: '当前选择已保留，请让医生检查设备。',
    endedTitle: '本次问诊已结束',
    endedHint: '本屏中的临时问题和回答已清除。',
    questionLabel: '医生提问',
    singleHint: '请选择一个答案，再确认提交',
    multiHint: '可以选择多个答案，再确认提交',
    numberHint: '请输入或选择数字',
    dateHint: '请选择日期',
    durationHint: '请输入时长并选择单位',
    textHint: '请输入简短说明',
    textFallback: '此版本暂不使用屏幕键盘。请让医生协助记录您的补充说明。',
    askToRecord: '请医生协助记录',
    submit: '确认提交',
    submitting: '正在发送',
    explain: '请医生解释',
    explainSent: '已通知医生，请稍候',
    skip: '跳过本题',
    skipConfirmTitle: '确定跳过这道问题吗？',
    skipConfirmHint: '医生会看到“患者跳过”，不会把它记录为空答案。',
    cancel: '返回作答',
    confirmSkip: '确认跳过',
    sentTitle: '回答已发送',
    sentHint: '请等待医生确认或发送下一题。',
    acknowledged: '医生已收到并确认',
    correction: '我需要更正',
    correctionSent: '已通知医生需要更正',
    sendFailed: '未发送成功，当前选择仍已保留',
    noOptions: '这道问题暂时无法显示答案选项，请让医生处理。',
    previousGroup: '上一组',
    nextGroup: '下一组',
    groupStatus: (current, total) => `第 ${current} 组，共 ${total} 组`,
    selectedCount: (count) => `已选 ${count} 项`,
    privacy: '仅在本机处理，不提供诊断结论',
    minutes: '分钟',
    hours: '小时',
    days: '天',
    weeks: '周',
    deleteDigit: '删除',
  },
  'en-US': {
    patient: 'Patient screen',
    session: 'Session',
    missingTitle: 'Waiting for a consultation',
    missingHint: 'Open the patient link created on the clinician screen.',
    connectingTitle: 'Connecting to the clinician',
    connectingHint: 'Please wait. No other action is needed.',
    waitingTitle: 'Connected. Please wait for a question',
    waitingHint: 'The next question will appear here automatically.',
    disconnectedTitle: 'Connection lost',
    disconnectedHint: 'Your current selection is saved. Please ask the clinician to check the device.',
    endedTitle: 'This consultation has ended',
    endedHint: 'Temporary questions and answers have been cleared from this screen.',
    questionLabel: 'Clinician question',
    singleHint: 'Choose one answer, then confirm',
    multiHint: 'You may choose more than one answer, then confirm',
    numberHint: 'Enter or choose a number',
    dateHint: 'Choose a date',
    durationHint: 'Enter a duration and choose a unit',
    textHint: 'Enter a short note',
    textFallback: 'The on-screen keyboard is not enabled in this version. Ask the clinician to record your note.',
    askToRecord: 'Ask clinician to record',
    submit: 'Confirm answer',
    submitting: 'Sending',
    explain: 'Ask for an explanation',
    explainSent: 'The clinician has been notified',
    skip: 'Skip this question',
    skipConfirmTitle: 'Skip this question?',
    skipConfirmHint: 'The clinician will see that you skipped it. It will not be stored as a blank answer.',
    cancel: 'Return to question',
    confirmSkip: 'Confirm skip',
    sentTitle: 'Answer sent',
    sentHint: 'Please wait for the clinician to confirm or send the next question.',
    acknowledged: 'The clinician has received and confirmed it',
    correction: 'I need to correct this',
    correctionSent: 'The clinician has been notified',
    sendFailed: 'The answer was not sent. Your selection is still saved.',
    noOptions: 'The answer choices are unavailable. Please ask the clinician for help.',
    previousGroup: 'Previous',
    nextGroup: 'Next',
    groupStatus: (current, total) => `Group ${current} of ${total}`,
    selectedCount: (count) => `${count} selected`,
    privacy: 'Processed on this device. No diagnosis is provided.',
    minutes: 'minutes',
    hours: 'hours',
    days: 'days',
    weeks: 'weeks',
    deleteDigit: 'Delete',
  },
}

const emptyDraft: AnswerDraft = {
  question: null,
  selectedCodes: [],
  inputValue: '',
  durationUnit: 'minutes',
  submissionState: 'draft',
  submittedText: '',
  acknowledged: false,
}

const optionPageSize = 6

function localeFromLanguage(language: string): SupportedPatientLocale {
  return language.startsWith('en') ? 'en-US' : 'zh-CN'
}

function storageKey(sessionId?: string) {
  return sessionId ? `hering.patient.${sessionId}` : null
}

function readStoredDraft(sessionId?: string): AnswerDraft {
  const key = storageKey(sessionId)
  if (!key) return emptyDraft
  try {
    const stored = window.sessionStorage.getItem(key)
    return stored ? { ...emptyDraft, ...(JSON.parse(stored) as Partial<AnswerDraft>) } : emptyDraft
  } catch {
    return emptyDraft
  }
}

function parseQuestion(event?: RealtimeEnvelope | null): QuestionSentPayload | null {
  if (event?.type !== 'question.sent' || !event.payload) return null
  const payload = event.payload
  if (
    typeof payload.question_id !== 'string'
    || typeof payload.field !== 'string'
    || typeof payload.answer_type !== 'string'
    || typeof payload.knowledge_version !== 'string'
    || typeof payload.prompt !== 'object'
    || payload.prompt === null
    || !Array.isArray(payload.options)
  ) {
    return null
  }
  return payload as unknown as QuestionSentPayload
}

function localizedText(
  text: { zh: string; en: string },
  locale: SupportedPatientLocale,
) {
  return locale === 'en-US' ? text.en : text.zh
}

function questionHint(question: QuestionSentPayload, copy: PatientCopy) {
  if (question.answer_type === 'single_choice') return copy.singleHint
  if (question.answer_type === 'multi_choice') return copy.multiHint
  if (question.answer_type === 'number') return copy.numberHint
  if (question.answer_type === 'date_or_relative') return copy.dateHint
  if (question.answer_type === 'duration') return copy.durationHint
  return copy.textHint
}

function optionDisplay(
  options: ClinicalAnswerOption[],
  codes: string[],
  locale: SupportedPatientLocale,
) {
  return codes
    .map((code) => options.find((option) => option.code === code))
    .filter((option): option is ClinicalAnswerOption => Boolean(option))
    .map((option) => localizedText(option.label, locale))
    .join('、')
}

export function PatientWorkspace({
  status,
  sessionId,
  lastEvent,
  onSendEvent,
}: PatientWorkspaceProps) {
  const { t, i18n } = useTranslation()
  const locale = localeFromLanguage(i18n.language)
  const copy = copyByLocale[locale]
  const [draft, setDraft] = useState<AnswerDraft>(() => readStoredDraft(sessionId))
  const [optionPage, setOptionPage] = useState(0)
  const [notice, setNotice] = useState('')
  const [skipConfirmOpen, setSkipConfirmOpen] = useState(false)
  const [ended, setEnded] = useState(false)

  const question = draft.question
  const optionPages = Math.max(1, Math.ceil((question?.options.length ?? 0) / optionPageSize))
  const visibleOptions = useMemo(
    () => question?.options.slice(
      optionPage * optionPageSize,
      (optionPage + 1) * optionPageSize,
    ) ?? [],
    [optionPage, question],
  )

  useEffect(() => {
    const key = storageKey(sessionId)
    if (!key || ended) return
    window.sessionStorage.setItem(key, JSON.stringify(draft))
  }, [draft, ended, sessionId])

  useEffect(() => {
    const incomingQuestion = parseQuestion(lastEvent)
    if (incomingQuestion) {
      setEnded(false)
      setSkipConfirmOpen(false)
      setOptionPage(0)
      setNotice('')
      setDraft((current) => current.question?.question_id === incomingQuestion.question_id
        ? { ...current, question: incomingQuestion }
        : { ...emptyDraft, question: incomingQuestion })
      return
    }
    if (lastEvent?.type === 'answer.received') {
      if (lastEvent.payload?.question_id === question?.question_id) {
        setDraft((current) => ({ ...current, submissionState: 'submitted' }))
      }
      return
    }
    if (lastEvent?.type === 'answer.acknowledged') {
      if (lastEvent.payload?.question_id === question?.question_id) {
        setDraft((current) => ({ ...current, acknowledged: true }))
      }
      return
    }
    if (lastEvent?.type === 'question.cancelled') {
      if (lastEvent.payload?.question_id === question?.question_id) {
        setDraft(emptyDraft)
      }
      return
    }
    if (lastEvent?.type === 'session.ended') {
      const key = storageKey(sessionId)
      if (key) window.sessionStorage.removeItem(key)
      setDraft(emptyDraft)
      setEnded(true)
    }
  }, [lastEvent, question?.question_id, sessionId])

  const changeLanguage = (nextLanguage: SupportedPatientLocale) => {
    void i18n.changeLanguage(nextLanguage)
    onSendEvent('locale.changed', { locale: nextLanguage })
  }

  const toggleOption = (code: string) => {
    if (!question || draft.submissionState !== 'draft') return
    setNotice('')
    setDraft((current) => {
      if (question.answer_type === 'single_choice') {
        return { ...current, selectedCodes: [code] }
      }
      const selected = current.selectedCodes.includes(code)
        ? current.selectedCodes.filter((item) => item !== code)
        : [...current.selectedCodes, code]
      return { ...current, selectedCodes: selected }
    })
  }

  const isComplete = useMemo(() => {
    if (!question) return false
    if (question.answer_type === 'single_choice' || question.answer_type === 'multi_choice') {
      return draft.selectedCodes.length > 0
    }
    if (question.answer_type === 'duration') {
      return draft.inputValue.trim().length > 0 && draft.durationUnit.length > 0
    }
    return draft.inputValue.trim().length > 0
  }, [draft.durationUnit, draft.inputValue, draft.selectedCodes.length, question])

  const answerDisplayText = () => {
    if (!question) return ''
    if (question.answer_type === 'single_choice' || question.answer_type === 'multi_choice') {
      return optionDisplay(question.options, draft.selectedCodes, locale)
    }
    if (question.answer_type === 'duration') {
      const unitLabel = draft.durationUnit === 'minutes'
        ? copy.minutes
        : draft.durationUnit === 'hours'
          ? copy.hours
          : draft.durationUnit === 'days'
            ? copy.days
            : copy.weeks
      return `${draft.inputValue} ${unitLabel}`
    }
    if (question.answer_type === 'number' && question.unit === 'Cel') {
      return `${draft.inputValue} ℃`
    }
    return draft.inputValue
  }

  const structuredValue = () => {
    if (!question) return null
    if (question.answer_type === 'single_choice') return draft.selectedCodes[0]
    if (question.answer_type === 'multi_choice') return draft.selectedCodes
    if (question.answer_type === 'duration') {
      return { value: Number(draft.inputValue), unit: draft.durationUnit }
    }
    if (question.answer_type === 'number') return Number(draft.inputValue)
    return draft.inputValue
  }

  const submitAnswer = (answerState: AnswerSubmittedPayload['answer_state'] = 'answered') => {
    if (!question || status !== 'connected') return
    const displayText = answerState === 'skipped'
      ? copy.skip
      : answerDisplayText()
    const payload: AnswerSubmittedPayload = {
      question_id: question.question_id,
      answer_type: question.answer_type,
      structured_value: answerState === 'skipped' ? null : structuredValue(),
      display_text: displayText,
      answer_state: answerState,
      patient_language: locale,
    }
    if (!onSendEvent('answer.submitted', payload)) {
      setNotice(copy.sendFailed)
      return
    }
    setSkipConfirmOpen(false)
    setNotice('')
    setDraft((current) => ({
      ...current,
      submissionState: 'submitting',
      submittedText: displayText,
    }))
  }

  const requestExplanation = () => {
    if (!question || status !== 'connected') return
    if (onSendEvent('explanation.requested', { question_id: question.question_id })) {
      setNotice(copy.explainSent)
    }
  }

  const requestCorrection = () => {
    if (!question || status !== 'connected') return
    if (onSendEvent('answer.correction_requested', { question_id: question.question_id })) {
      setNotice(copy.correctionSent)
    }
  }

  const appendNumber = (digit: string) => {
    setDraft((current) => {
      if (digit === '.' && current.inputValue.includes('.')) return current
      if (current.inputValue.length >= 6) return current
      return { ...current, inputValue: `${current.inputValue}${digit}` }
    })
  }

  const renderChoiceInput = () => {
    if (!question) return null
    if (question.options.length === 0) {
      return <div className="patient-input-error" role="alert">{copy.noOptions}</div>
    }
    const compactGrid = question.answer_type === 'multi_choice' || question.options.length > 4
    return (
      <div className="patient-options-frame">
        <div className={`patient-options${compactGrid ? ' patient-options--grid' : ''}`}>
          {visibleOptions.map((option) => {
            const selected = draft.selectedCodes.includes(option.code)
            return (
              <button
                key={option.code}
                type="button"
                className={`patient-option${selected ? ' patient-option--selected' : ''}`}
                aria-pressed={selected}
                onClick={() => toggleOption(option.code)}
              >
                <span className="patient-option__indicator" aria-hidden="true">
                  {selected ? '✓' : ''}
                </span>
                <span>{localizedText(option.label, locale)}</span>
              </button>
            )
          })}
        </div>
        {optionPages > 1 && (
          <div className="patient-option-pages">
            <button
              type="button"
              disabled={optionPage === 0}
              onClick={() => setOptionPage((page) => Math.max(0, page - 1))}
            >
              {copy.previousGroup}
            </button>
            <span>
              {copy.groupStatus(optionPage + 1, optionPages)}
              {draft.selectedCodes.length > 0 && `，${copy.selectedCount(draft.selectedCodes.length)}`}
            </span>
            <button
              type="button"
              disabled={optionPage === optionPages - 1}
              onClick={() => setOptionPage((page) => Math.min(optionPages - 1, page + 1))}
            >
              {copy.nextGroup}
            </button>
          </div>
        )}
      </div>
    )
  }

  const renderNumberInput = () => {
    if (!question) return null
    if (question.unit === '0-10') {
      return (
        <div className="patient-scale" aria-label={copy.numberHint}>
          {Array.from({ length: 11 }, (_, value) => (
            <button
              key={value}
              type="button"
              className={draft.inputValue === String(value) ? 'patient-scale__selected' : ''}
              aria-pressed={draft.inputValue === String(value)}
              onClick={() => setDraft((current) => ({ ...current, inputValue: String(value) }))}
            >
              {value}
            </button>
          ))}
        </div>
      )
    }
    return (
      <div className="patient-number-entry">
        <output>{draft.inputValue || '0'}{question.unit === 'Cel' ? ' ℃' : ''}</output>
        <div className="patient-keypad">
          {['1', '2', '3', '4', '5', '6', '7', '8', '9', '.', '0'].map((digit) => (
            <button key={digit} type="button" onClick={() => appendNumber(digit)}>{digit}</button>
          ))}
          <button
            type="button"
            onClick={() => setDraft((current) => ({
              ...current,
              inputValue: current.inputValue.slice(0, -1),
            }))}
          >
            {copy.deleteDigit}
          </button>
        </div>
      </div>
    )
  }

  const renderInput = () => {
    if (!question) return null
    if (question.answer_type === 'single_choice' || question.answer_type === 'multi_choice') {
      return renderChoiceInput()
    }
    if (question.answer_type === 'number') return renderNumberInput()
    if (question.answer_type === 'duration') {
      return (
        <div className="patient-duration">
          <label>
            <span>{copy.durationHint}</span>
            <input
              type="number"
              min="0"
              inputMode="numeric"
              value={draft.inputValue}
              onChange={(event) => setDraft((current) => ({
                ...current,
                inputValue: event.target.value,
              }))}
            />
          </label>
          <div className="patient-duration__units" role="group" aria-label={copy.durationHint}>
            {([
              ['minutes', copy.minutes],
              ['hours', copy.hours],
              ['days', copy.days],
              ['weeks', copy.weeks],
            ] as const).map(([code, label]) => (
              <button
                key={code}
                type="button"
                className={draft.durationUnit === code ? 'patient-duration__selected' : ''}
                aria-pressed={draft.durationUnit === code}
                onClick={() => setDraft((current) => ({ ...current, durationUnit: code }))}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )
    }
    if (question.answer_type === 'date_or_relative') {
      return (
        <label className="patient-date">
          <span>{copy.dateHint}</span>
          <input
            type="date"
            value={draft.inputValue}
            onChange={(event) => setDraft((current) => ({
              ...current,
              inputValue: event.target.value,
            }))}
          />
        </label>
      )
    }
    return (
      <div className="patient-text-fallback" role="note">
        <span aria-hidden="true">i</span>
        <p>{copy.textFallback}</p>
      </div>
    )
  }

  const waitingContent = ended
    ? { title: copy.endedTitle, hint: copy.endedHint, state: 'ended' }
    : status === 'idle'
      ? { title: copy.missingTitle, hint: copy.missingHint, state: 'idle' }
      : status === 'connecting'
        ? { title: copy.connectingTitle, hint: copy.connectingHint, state: 'connecting' }
        : status === 'disconnected'
          ? { title: copy.disconnectedTitle, hint: copy.disconnectedHint, state: 'disconnected' }
          : { title: copy.waitingTitle, hint: copy.waitingHint, state: 'waiting' }

  const showQuestion = question && !ended
  const showSubmitted = showQuestion && draft.submissionState === 'submitted'

  return (
    <main className="patient-workspace">
      <header className="patient-header">
        <div className="patient-brand">
          <span className="patient-brand__mark" aria-hidden="true">H</span>
          <div>
            <strong>{t('brand')}</strong>
            <span>{copy.patient}</span>
          </div>
        </div>
        <div className={`patient-connection patient-connection--${status}`} role="status">
          <span aria-hidden="true" />
          {ended
            ? copy.endedTitle
            : status === 'connected'
              ? showSubmitted
                ? copy.sentTitle
                : showQuestion
                  ? copy.questionLabel
                  : copy.waitingTitle
              : waitingContent.title}
        </div>
        <div className="patient-header__tools">
          {sessionId && <span>{copy.session} {sessionId.slice(0, 8)}</span>}
          <label className="patient-language">
            <span className="patient-sr-only">{t('language')}</span>
            <select
              aria-label={t('language')}
              value={locale}
              onChange={(event) => changeLanguage(event.target.value as SupportedPatientLocale)}
            >
              <option value="zh-CN">简体中文</option>
              <option value="en-US">English</option>
            </select>
          </label>
        </div>
      </header>

      {!showQuestion && (
        <section className={`patient-waiting patient-waiting--${waitingContent.state}`}>
          <div className="patient-waiting__signal" aria-hidden="true">
            <span /><span /><span />
          </div>
          <h1>{waitingContent.title}</h1>
          <p>{waitingContent.hint}</p>
        </section>
      )}

      {showQuestion && !showSubmitted && (
        <section className="patient-question">
          <header className="patient-question__header">
            <div>
              <span>{copy.questionLabel}</span>
              <h1>{localizedText(question.prompt, locale)}</h1>
            </div>
            <p>{questionHint(question, copy)}</p>
          </header>
          <div className="patient-question__input">
            {renderInput()}
          </div>
          {status === 'disconnected' && (
            <div className="patient-offline-banner" role="alert">
              <strong>{copy.disconnectedTitle}</strong>
              <span>{copy.disconnectedHint}</span>
            </div>
          )}
        </section>
      )}

      {showSubmitted && (
        <section className="patient-submitted" aria-live="polite">
          <span>{draft.acknowledged ? copy.acknowledged : copy.sentTitle}</span>
          <h1>{draft.submittedText}</h1>
          <p>{copy.sentHint}</p>
          {notice && <div className="patient-notice">{notice}</div>}
        </section>
      )}

      <footer className="patient-actions">
        {showQuestion && !showSubmitted ? (
          <>
            <div className="patient-actions__secondary">
              <button
                type="button"
                disabled={status !== 'connected' || draft.submissionState !== 'draft'}
                onClick={requestExplanation}
              >
                {question.answer_type === 'free_text' ? copy.askToRecord : copy.explain}
              </button>
              <button
                type="button"
                disabled={status !== 'connected' || draft.submissionState !== 'draft'}
                onClick={() => setSkipConfirmOpen(true)}
              >
                {copy.skip}
              </button>
            </div>
            <div className="patient-actions__status" aria-live="polite">
              {notice || (draft.selectedCodes.length > 0
                ? copy.selectedCount(draft.selectedCodes.length)
                : '')}
            </div>
            <button
              type="button"
              className="patient-primary-action"
              disabled={!isComplete || status !== 'connected' || draft.submissionState !== 'draft'}
              onClick={() => submitAnswer()}
            >
              {draft.submissionState === 'submitting' ? copy.submitting : copy.submit}
            </button>
          </>
        ) : showSubmitted ? (
          <>
            <button
              type="button"
              className="patient-correction-action"
              disabled={status !== 'connected'}
              onClick={requestCorrection}
            >
              {copy.correction}
            </button>
            <span className="patient-actions__waiting">
              {notice || (draft.acknowledged ? copy.acknowledged : copy.sentHint)}
            </span>
          </>
        ) : (
          <span className="patient-actions__privacy">{copy.privacy}</span>
        )}
      </footer>

      {skipConfirmOpen && (
        <section className="patient-dialog-backdrop" role="dialog" aria-modal="true" aria-labelledby="skip-title">
          <div className="patient-dialog">
            <h2 id="skip-title">{copy.skipConfirmTitle}</h2>
            <p>{copy.skipConfirmHint}</p>
            <div>
              <button type="button" onClick={() => setSkipConfirmOpen(false)}>{copy.cancel}</button>
              <button type="button" className="patient-dialog__confirm" onClick={() => submitAnswer('skipped')}>
                {copy.confirmSkip}
              </button>
            </div>
          </div>
        </section>
      )}
    </main>
  )
}
