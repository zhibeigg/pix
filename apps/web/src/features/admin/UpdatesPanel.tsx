import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../../api'
import { useI18n } from '../../i18n'
import type { AdminUpdateStatus, UpdateOperation } from '../../types'
import { Alert } from '../../components/ui/alert'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Input } from '../../components/ui/input'
import { PixField } from '../../components/pix/PixField'

const TERMINAL_OPERATION_STATES = new Set(['succeeded', 'failed', 'rolled_back', 'rollback_failed'])
const APPLY_STEPS = ['requested', 'preflight', 'verifying', 'pulling', 'backing_up', 'stopping', 'migrating', 'deploying', 'health_check', 'succeeded', 'failed', 'rolling_back', 'rolled_back', 'rollback_failed']
const ROLLBACK_STEPS = ['requested', 'rolling_back', 'health_check', 'rolled_back', 'failed', 'rollback_failed']

function idempotencyKey(prefix: string) {
  const random = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `${prefix}-${random}`
}

function isOperationActive(operation: UpdateOperation | null) {
  return Boolean(operation && !TERMINAL_OPERATION_STATES.has(operation.state))
}

function stepState(operation: UpdateOperation, key: string): 'pending' | 'running' | 'succeeded' | 'failed' {
  const visited = operation.transitions.includes(key)
  if (operation.state === key) {
    if (key === 'failed' || key === 'rollback_failed') return 'failed'
    if (TERMINAL_OPERATION_STATES.has(key)) return 'succeeded'
    return 'running'
  }
  if (visited) return key === 'failed' || key === 'rollback_failed' ? 'failed' : 'succeeded'
  return 'pending'
}

export function UpdatesPanel({ token }: { token: string }) {
  const { t } = useI18n()
  const [status, setStatus] = useState<AdminUpdateStatus | null>(null)
  const [operation, setOperation] = useState<UpdateOperation | null>(null)
  const [loading, setLoading] = useState(true)
  const [checking, setChecking] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [password, setPassword] = useState('')
  const [targetConfirmation, setTargetConfirmation] = useState('')
  const [rollbackConfirmation, setRollbackConfirmation] = useState('')

  const loadStatus = useCallback(async () => {
    setError('')
    try {
      const result = await api.adminUpdateStatus(token)
      setStatus(result)
      setOperation(result.operation)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { void loadStatus() }, [loadStatus])

  useEffect(() => {
    if (!isOperationActive(operation)) return
    let stopped = false
    let timer = 0
    const poll = async () => {
      if (stopped) return
      if (document.visibilityState === 'hidden') {
        timer = window.setTimeout(poll, 2500)
        return
      }
      try {
        const next = await api.adminUpdateOperation(token, operation!.operation_id)
        if (stopped) return
        setOperation(next)
        if (isOperationActive(next)) timer = window.setTimeout(poll, 1500)
        else void loadStatus()
      } catch (reason) {
        if (!stopped) {
          setError(reason instanceof Error ? reason.message : String(reason))
          timer = window.setTimeout(poll, 4000)
        }
      }
    }
    timer = window.setTimeout(poll, 1000)
    return () => { stopped = true; window.clearTimeout(timer) }
  }, [loadStatus, operation, token])

  const release = status?.latest_release ?? null
  const targetVersion = release?.version ?? ''
  const manifestSha = release?.manifest_sha256 ?? ''
  const agentOnline = status?.agent.available === true
  const operationActive = isOperationActive(operation)
  const canApply = status?.can_apply === true && targetConfirmation.trim() === targetVersion && Boolean(password) && !submitting && !operationActive
  const canRollback = status?.can_rollback === true && rollbackConfirmation.trim() === 'ROLLBACK' && Boolean(password) && !submitting && !operationActive

  const operationStatusLabel = useMemo(
    () => operation ? t(`admin.status.updateOperation.${operation.state}`, { defaultValue: operation.state }) : '',
    [operation, t],
  )
  const timeline = operation ? (operation.action === 'rollback' ? ROLLBACK_STEPS : APPLY_STEPS) : []

  async function checkForUpdates() {
    setChecking(true)
    setError('')
    setNotice('')
    try {
      const result = await api.checkAdminUpdates(token)
      setStatus(result)
      setOperation(result.operation)
      setNotice(t('admin.updates.messages.checkComplete'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setChecking(false)
    }
  }

  async function authenticate() {
    const result = await api.stepUpAdminUpdate(token, password)
    if (!result.ok) throw new Error(t('admin.updates.errors.stepUpRejected'))
  }

  async function applyUpdate() {
    if (!canApply) return
    setSubmitting(true)
    setError('')
    setNotice('')
    try {
      await authenticate()
      const result = await api.applyAdminUpdate(token, {
        target_version: targetVersion,
        expected_manifest_sha256: manifestSha,
        idempotency_key: idempotencyKey('update'),
      })
      setStatus(result)
      setOperation(result.operation)
      setPassword('')
      setTargetConfirmation('')
      setNotice(t('admin.updates.messages.applyQueued'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setSubmitting(false)
    }
  }

  async function rollback() {
    if (!canRollback) return
    setSubmitting(true)
    setError('')
    setNotice('')
    try {
      await authenticate()
      const result = await api.rollbackAdminUpdate(token, idempotencyKey('rollback'))
      setStatus(result)
      setOperation(result.operation)
      setPassword('')
      setRollbackConfirmation('')
      setNotice(t('admin.updates.messages.rollbackQueued'))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading && !status) return <Alert variant="info">{t('admin.common.loading')}</Alert>

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{t('admin.updates.title')}</h2>
          <p className="text-sm text-muted-foreground">{t('admin.updates.description')}</p>
        </div>
        <Button type="button" variant="outline" onClick={() => void checkForUpdates()} disabled={checking || operationActive || status?.check_enabled === false}>{checking ? t('admin.updates.checking') : t('admin.updates.check')}</Button>
      </div>

      {error && <Alert variant="destructive">{error}</Alert>}
      {notice && <Alert variant="success">{notice}</Alert>}
      {status?.error && <Alert variant="warning">{t(`admin.updates.backendErrors.${status.error}`, { defaultValue: status.error })}</Alert>}
      {!agentOnline && <Alert variant="warning">{t('admin.updates.agentOfflineWarning')}</Alert>}
      {status?.update_available && !status.can_apply && <Alert variant="info">{t('admin.updates.readOnlyWarning')}</Alert>}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard label={t('admin.updates.currentVersion')} value={status?.current_version || '—'} />
        <StatusCard label={t('admin.updates.latestVersion')} value={targetVersion || '—'} badge={status?.update_available ? t('admin.updates.available') : t('admin.updates.upToDate')} />
        <StatusCard label={t('admin.updates.agent')} value={status?.agent.updater_version || status?.agent.state || '—'} badge={agentOnline ? t('admin.status.agent.online') : t('admin.status.agent.offline')} />
        <StatusCard label={t('admin.updates.manifest')} value={release?.alembic_head || '—'} sub={release?.manifest_sha256 || t('admin.updates.noManifest')} />
      </div>

      {release?.notes && <details className="rounded-lg border border-border bg-muted/25 p-3 text-sm"><summary className="cursor-pointer font-medium">{t('admin.updates.releaseNotes')}</summary><p className="mt-2 max-w-3xl leading-6 text-muted-foreground">{release.notes}</p></details>}

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="grid content-start gap-3 rounded-lg border border-border bg-card p-4">
          <div><h3 className="font-semibold">{t('admin.updates.applyTitle')}</h3><p className="text-sm text-muted-foreground">{t('admin.updates.applyDescription', { version: targetVersion || '—' })}</p></div>
          <PixField label={t('admin.updates.password')}><Input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></PixField>
          <PixField label={t('admin.updates.typeVersion', { version: targetVersion || '—' })}><Input value={targetConfirmation} onChange={(event) => setTargetConfirmation(event.target.value)} /></PixField>
          <Button type="button" onClick={() => void applyUpdate()} disabled={!canApply}>{submitting ? t('admin.common.submitting') : t('admin.updates.apply')}</Button>
        </section>

        <section className="grid content-start gap-3 rounded-lg border border-border bg-card p-4">
          <div><h3 className="font-semibold">{t('admin.updates.rollbackTitle')}</h3><p className="text-sm text-muted-foreground">{t('admin.updates.rollbackDescription')}</p></div>
          <PixField label={t('admin.updates.password')}><Input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></PixField>
          <PixField label={t('admin.updates.typeRollback')}><Input value={rollbackConfirmation} onChange={(event) => setRollbackConfirmation(event.target.value)} /></PixField>
          <Button type="button" variant="destructive" onClick={() => void rollback()} disabled={!canRollback}>{submitting ? t('admin.common.submitting') : t('admin.updates.rollback')}</Button>
        </section>
      </div>

      <section className="grid gap-3 rounded-lg border border-border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">{t('admin.updates.timeline')}</h3>{operation && <Badge variant={operation.state === 'succeeded' || operation.state === 'rolled_back' ? 'success' : operation.state === 'failed' || operation.state === 'rollback_failed' ? 'danger' : 'info'}>{operationStatusLabel}</Badge>}</div>
        {!operation ? <p className="text-sm text-muted-foreground">{t('admin.updates.noOperation')}</p> : (
          <div className="grid gap-2">
            <p className="text-xs text-muted-foreground">#{operation.operation_id} · {operation.action} · {operation.target_version || '—'}</p>
            {timeline.map((key) => {
              const state = stepState(operation, key)
              return <div key={key} className="grid gap-1 rounded-md border border-border bg-muted/30 px-3 py-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><p className="text-sm font-medium">{t(`admin.updates.steps.${key}`, { defaultValue: key })}</p><Badge variant={state === 'succeeded' ? 'success' : state === 'failed' ? 'danger' : state === 'running' ? 'warning' : 'outline'}>{t(`admin.status.updateStep.${state}`, { defaultValue: state })}</Badge></div>
            })}
            {operation.error && <Alert variant="destructive">{operation.error}</Alert>}
          </div>
        )}
      </section>
    </div>
  )
}

function StatusCard({ label, value, badge, sub }: { label: string; value: string; badge?: string; sub?: string }) {
  return <div className="min-w-0 rounded-lg border border-border bg-card p-3"><p className="text-xs text-muted-foreground">{label}</p><div className="mt-1 flex min-w-0 items-center gap-2"><p className="truncate text-lg font-semibold" title={value}>{value}</p>{badge && <Badge variant="outline">{badge}</Badge>}</div>{sub && <p className="mt-1 truncate text-xs text-muted-foreground" title={sub}>{sub}</p>}</div>
}
