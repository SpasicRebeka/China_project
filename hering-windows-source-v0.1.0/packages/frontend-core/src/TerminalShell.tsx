import type { Role } from '@hering/contracts'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { ConnectionStatus } from './realtime'

interface TerminalShellProps {
  role: Role
  status: ConnectionStatus
  sessionId?: string
  patientUrl?: string
  error?: boolean
  lastEventType?: string
  onSendTest?: () => void
}

export function TerminalShell({
  role,
  status,
  sessionId,
  patientUrl,
  error,
  lastEventType,
  onSendTest,
}: TerminalShellProps) {
  const { t, i18n } = useTranslation()
  const [copied, setCopied] = useState(false)
  const statusLabel = status === 'idle' ? 'missingSession' : status

  const copy = async () => {
    if (!patientUrl) return
    await navigator.clipboard.writeText(patientUrl)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1200)
  }

  return (
    <main className={`terminal terminal--${role}`}>
      <header className="terminal__header">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true">H</span>
          <div>
            <strong>{t('brand')}</strong>
            <span>{t('subtitle')}</span>
          </div>
        </div>
        <div className="header-tools">
          <label>
            <span>{t('language')}</span>
            <select value={i18n.language} onChange={(event) => void i18n.changeLanguage(event.target.value)}>
              <option value="zh-CN">简体中文</option>
              <option value="zh-TW">繁體中文</option>
              <option value="en-US">English</option>
            </select>
          </label>
          <span className={`status status--${status}`}>
            <i aria-hidden="true" /> {t(statusLabel)}
          </span>
        </div>
      </header>

      <section className="terminal__body">
        <div className="role-label">{t(role)}</div>
        <div className="hero-card">
          <div className="hero-card__signal" aria-hidden="true">
            <span /><span /><span />
          </div>
          <h1>{error ? t('createFailed') : status === 'idle' ? t('missingSession') : t('ready')}</h1>
          <p>{status === 'idle' ? t('missingSessionHint') : t('readyHint')}</p>

          {sessionId && (
            <dl className="session-line">
              <dt>{t('session')}</dt>
              <dd>{sessionId.slice(0, 8)}</dd>
            </dl>
          )}

          {patientUrl && (
            <div className="join-panel">
              <span>{t('patientLink')}</span>
              <code>{patientUrl}</code>
              <button type="button" className="button button--secondary" onClick={() => void copy()}>
                {copied ? t('copied') : t('copyLink')}
              </button>
            </div>
          )}

          {sessionId && (
            <div className="actions">
              <button type="button" className="button" disabled={status !== 'connected'} onClick={onSendTest}>
                {t('sendTest')}
              </button>
              <div className="event-readout">
                <span>{t('lastEvent')}</span>
                <strong>{lastEventType ?? t('noEvent')}</strong>
              </div>
            </div>
          )}
        </div>
      </section>

      <footer>{t('privacy')}</footer>
    </main>
  )
}

