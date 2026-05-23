import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { ArrowRightLeft, Banknote, Clock3, Copy, Gift, RefreshCw, Users, WalletCards } from 'lucide-react'
import { api } from '../api'
import { useI18n } from '../i18n'
import { formatDateTime } from '../lib/utils'
import type { ReferralInvite, ReferralReward, ReferralSettlement, ReferralSummary } from '../types'
import { Alert } from '../components/ui/alert'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { PageHeader } from '../components/PageHeader'
import { PixPanel } from '../components/pix/PixPanel'

const REWARD_TABS = ['invites', 'rewards', 'settlements'] as const
type RewardTab = typeof REWARD_TABS[number]
type Translate = ReturnType<typeof useI18n>['t']

type RewardsPageProps = {
  token: string
  onRefresh: () => void | Promise<void>
}

export function RewardsPage({ token, onRefresh }: RewardsPageProps) {
  const { t } = useI18n()
  const [summary, setSummary] = useState<ReferralSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [tab, setTab] = useState<RewardTab>('invites')

  async function load() {
    if (!token) return
    setLoading(true)
    setError('')
    try {
      setSummary(await api.referralSummary(token))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('rewards.errors.loadFailed'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [token])

  const primaryCurrency = summary?.primary_currency ?? 'cny'
  const available = summary?.available_cents ?? 0
  const rate = ((summary?.commission_rate_bps ?? 1000) / 100).toFixed(0)
  const tabCount = useMemo(() => ({
    invites: summary?.invites.length ?? 0,
    rewards: summary?.rewards.length ?? 0,
    settlements: summary?.settlements.length ?? 0,
  }), [summary])

  async function copyInviteLink() {
    if (!summary?.invite_url) return
    try {
      await navigator.clipboard.writeText(summary.invite_url)
      setNotice(t('rewards.messages.linkCopied'))
    } catch {
      setError(t('rewards.errors.copyFailed'))
    }
  }

  async function transferRewards() {
    if (!summary || available <= 0) return
    setWorking(true)
    setNotice('')
    setError('')
    try {
      const settlement = await api.transferReferralRewards(token, primaryCurrency)
      setNotice(t('rewards.messages.transferSuccess', { count: settlement.credits }))
      await load()
      await onRefresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('rewards.errors.transferFailed'))
    } finally {
      setWorking(false)
    }
  }

  async function withdrawRewards() {
    if (!summary || available <= 0) return
    if (!window.confirm(t('rewards.withdrawConfirm'))) return
    setWorking(true)
    setNotice('')
    setError('')
    try {
      await api.withdrawReferralRewards(token, available, primaryCurrency, t('rewards.withdrawNote'))
      setNotice(t('rewards.messages.withdrawSubmitted'))
      await load()
      await onRefresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('rewards.errors.withdrawFailed'))
    } finally {
      setWorking(false)
    }
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        eyebrow={t('rewards.eyebrow')}
        title={t('rewards.title')}
        description={t('rewards.description')}
        action={<Button variant="outline" disabled={loading} onClick={() => void load()}><RefreshCw />{t('common.refresh')}</Button>}
      />

      <PixPanel>
        <div className="reward-summary-surface motion-ambient-flow overflow-hidden rounded-xl border">
          <div className="relative grid gap-6 p-5 sm:p-6">
            <div className="reward-summary-overlay pointer-events-none absolute inset-0" />
            <div className="relative flex flex-wrap items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="reward-summary-icon motion-attention-pop grid h-10 w-10 place-items-center rounded-full ring-1"><Gift className="h-5 w-5" /></div>
                <div>
                  <h2 className="reward-summary-title text-lg font-semibold">{t('rewards.statsTitle')}</h2>
                  <p className="reward-summary-subtitle text-sm">{t('rewards.currentRate', { rate })}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" className="reward-secondary-action" disabled={working || available <= 0} onClick={() => void withdrawRewards()}><Banknote />{t('rewards.actions.withdraw')}</Button>
                <Button size="sm" className="reward-primary-action" disabled={working || available <= 0} onClick={() => void transferRewards()}><ArrowRightLeft />{t('rewards.actions.transfer')}</Button>
              </div>
            </div>
            <div className="motion-list-stagger relative grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <RewardMetric icon={<Clock3 />} label={t('rewards.metrics.pending')} value={money(summary?.pending_cents ?? 0, primaryCurrency)} />
              <RewardMetric icon={<WalletCards />} label={t('rewards.metrics.available')} value={money(available, primaryCurrency)} />
              <RewardMetric icon={<Banknote />} label={t('rewards.metrics.total')} value={money(summary?.total_reward_cents ?? 0, primaryCurrency)} />
              <RewardMetric icon={<Users />} label={t('rewards.metrics.invited')} value={summary?.invited_count ?? 0} />
            </div>
            <div className="reward-link-bar relative grid gap-2 rounded-lg p-2 ring-1 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center">
              <span className="reward-link-label px-2 text-xs font-semibold">{t('rewards.inviteLink')}</span>
              <code className="reward-link-code motion-shimmer min-w-0 overflow-hidden text-ellipsis whitespace-nowrap rounded-md px-3 py-2 text-sm">{summary?.invite_url ?? t('rewards.generatingLink')}</code>
              <Button size="sm" disabled={!summary?.invite_url} onClick={() => void copyInviteLink()}><Copy />{t('common.copy')}</Button>
            </div>
          </div>
        </div>

        <div className="mt-4 grid gap-3">
          {notice && <Alert variant="success">{notice}</Alert>}
          {error && <Alert variant="destructive">{error}</Alert>}
          {!summary?.enabled && <Alert variant="warning">{t('rewards.disabled')}</Alert>}
        </div>
      </PixPanel>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <PixPanel>
          <div className="flex flex-wrap gap-2 border-b border-border pb-3 dark:border-white/10">
            {REWARD_TABS.map((item) => (
              <Button key={item} type="button" size="sm" variant={tab === item ? 'default' : 'ghost'} onClick={() => setTab(item)}>
                {tabLabel(item, t)}
                <Badge variant="secondary">{tabCount[item]}</Badge>
              </Button>
            ))}
          </div>
          <div className="mt-4">
            {loading ? <RewardEmpty title={t('rewards.loading')} /> : null}
            {!loading && tab === 'invites' && <InviteRows rows={summary?.invites ?? []} onCopy={copyInviteLink} />}
            {!loading && tab === 'rewards' && <RewardRows rows={summary?.rewards ?? []} />}
            {!loading && tab === 'settlements' && <SettlementRows rows={summary?.settlements ?? []} />}
          </div>
        </PixPanel>

        <PixPanel eyebrow={t('rewards.rulesEyebrow')} title={t('rewards.rulesTitle')}>
          <ul className="grid gap-3 text-sm leading-6 text-muted-foreground">
            <RuleItem>{t('rewards.rules.rate', { rate })}</RuleItem>
            <RuleItem>{t('rewards.rules.invite')}</RuleItem>
            <RuleItem>{t('rewards.rules.pending', { days: summary?.pending_days ?? 30 })}</RuleItem>
            <RuleItem>{t('rewards.rules.transfer')}</RuleItem>
            <RuleItem>{t('rewards.rules.withdrawal')}</RuleItem>
          </ul>
        </PixPanel>
      </div>
    </div>
  )
}

function RewardMetric({ icon, label, value }: { icon: ReactNode; label: ReactNode; value: ReactNode }) {
  return (
    <div className="reward-metric-card rounded-lg px-4 py-4 ring-1 backdrop-blur-sm">
      <div className="reward-metric-label flex items-center gap-2 [&_svg]:h-4 [&_svg]:w-4">{icon}<span className="text-xs font-semibold">{label}</span></div>
      <p className="reward-metric-value mt-3 text-3xl font-bold tabular-nums tracking-tight">{value}</p>
    </div>
  )
}

function InviteRows({ rows, onCopy }: { rows: ReferralInvite[]; onCopy: () => void }) {
  const { t } = useI18n()
  if (!rows.length) return <RewardEmpty title={t('rewards.empty.invites')} action={<Button size="sm" onClick={() => void onCopy()}><Copy />{t('rewards.empty.copyInvite')}</Button>} />
  return <div className="motion-list-stagger grid gap-2">{rows.map((row) => <RecordRow key={row.id} title={row.referred_user_display_name || row.referred_user_email} meta={row.referred_user_email} right={formatDateTime(row.created_at)} />)}</div>
}

function RewardRows({ rows }: { rows: ReferralReward[] }) {
  const { t } = useI18n()
  if (!rows.length) return <RewardEmpty title={t('rewards.empty.rewards')} />
  return <div className="motion-list-stagger grid gap-2">{rows.map((row) => <RecordRow key={row.id} title={money(row.amount_cents, row.currency)} meta={t('rewards.rewardMeta', { orderId: row.order_id, status: rewardStatus(row.status, t), email: row.referred_user_email })} right={formatDateTime(row.created_at)} />)}</div>
}

function SettlementRows({ rows }: { rows: ReferralSettlement[] }) {
  const { t } = useI18n()
  if (!rows.length) return <RewardEmpty title={t('rewards.empty.settlements')} />
  return <div className="motion-list-stagger grid gap-2">{rows.map((row) => <RecordRow key={row.id} title={settlementTitle(row, t)} meta={t('rewards.settlementMeta', { status: settlementStatus(row.status, t), note: row.note || t('rewards.noNote') })} right={formatDateTime(row.created_at)} />)}</div>
}

function RecordRow({ title, meta, right }: { title: ReactNode; meta: ReactNode; right: ReactNode }) {
  return (
    <div className="grid gap-2 rounded-lg border border-border bg-card px-4 py-3 transition-[background-color,border-color,box-shadow,transform] duration-[var(--motion-fast)] ease-[var(--ease-out-quart)] hover:-translate-y-0.5 hover:shadow-[0_12px_28px_-24px_rgba(15,15,15,.45)] sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center dark:border-white/10 dark:bg-white/5">
      <div className="min-w-0"><p className="truncate font-semibold">{title}</p><p className="mt-1 truncate text-sm text-muted-foreground">{meta}</p></div>
      <p className="text-xs text-muted-foreground">{right}</p>
    </div>
  )
}

function RewardEmpty({ title, action }: { title: ReactNode; action?: ReactNode }) {
  return <div className="motion-panel-enter grid min-h-56 place-items-center gap-3 rounded-lg border border-dashed border-border bg-muted/28 p-8 text-center dark:border-white/10 dark:bg-white/5"><Gift className="motion-float-soft h-12 w-12 text-muted-foreground" /><p className="text-sm text-muted-foreground">{title}</p>{action}</div>
}

function RuleItem({ children }: { children: ReactNode }) {
  return <li className="grid grid-cols-[10px_minmax(0,1fr)] gap-3"><span className="mt-2 h-2 w-2 rounded-full bg-emerald-500" />{children}</li>
}

function tabLabel(tab: RewardTab, t: Translate) {
  if (tab === 'invites') return t('rewards.tabs.invites')
  if (tab === 'rewards') return t('rewards.tabs.rewards')
  return t('rewards.tabs.settlements')
}

function rewardStatus(status: string, t: Translate) {
  if (status === 'pending') return t('rewards.rewardStatus.pending')
  if (status === 'available') return t('rewards.rewardStatus.available')
  if (status === 'settled') return t('rewards.rewardStatus.settled')
  return status
}

function settlementStatus(status: string, t: Translate) {
  if (status === 'pending') return t('rewards.settlementStatus.pending')
  if (status === 'completed') return t('rewards.settlementStatus.completed')
  return status
}

function settlementTitle(row: ReferralSettlement, t: Translate) {
  if (row.type === 'transfer') return t('rewards.settlementTitle.transfer', { count: row.credits })
  return t('rewards.settlementTitle.withdrawal', { amount: money(row.amount_cents, row.currency) })
}

function money(cents: number, currency = 'cny') {
  const value = (cents / 100).toFixed(2)
  const clean = currency.toLowerCase()
  if (clean === 'cny') return `¥${value}`
  if (clean === 'usd') return `$${value}`
  return `${clean.toUpperCase()} ${value}`
}
