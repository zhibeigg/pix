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

type RewardsPageProps = {
  token: string
  onRefresh: () => void | Promise<void>
}

export function RewardsPage({ token, onRefresh }: RewardsPageProps) {
  const { text } = useI18n()
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
      setError(err instanceof Error ? err.message : text('邀请奖励加载失败。', 'Failed to load referral rewards.'))
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
      setNotice(text('邀请链接已复制。', 'Invite link copied.'))
    } catch {
      setError(text('复制失败，请手动选中邀请链接。', 'Copy failed. Please select the invite link manually.'))
    }
  }

  async function transferRewards() {
    if (!summary || available <= 0) return
    setWorking(true)
    setNotice('')
    setError('')
    try {
      const settlement = await api.transferReferralRewards(token, primaryCurrency)
      setNotice(text(`已划转 ${settlement.credits} 点到余额。`, `${settlement.credits} credits transferred to your balance.`))
      await load()
      await onRefresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : text('划转失败。', 'Transfer failed.'))
    } finally {
      setWorking(false)
    }
  }

  async function withdrawRewards() {
    if (!summary || available <= 0) return
    if (!window.confirm(text('申请提现当前全部可用邀请收益？', 'Request withdrawal for all available referral rewards?'))) return
    setWorking(true)
    setNotice('')
    setError('')
    try {
      await api.withdrawReferralRewards(token, available, primaryCurrency, text('用户从邀请奖励页申请提现', 'User requested withdrawal from rewards page'))
      setNotice(text('提现申请已提交，等待人工处理。', 'Withdrawal request submitted for review.'))
      await load()
      await onRefresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : text('提现申请失败。', 'Withdrawal request failed.'))
    } finally {
      setWorking(false)
    }
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        eyebrow={text('邀请奖励', 'Referral rewards')}
        title={text('邀请好友，获得额外奖励', 'Invite friends and earn rewards')}
        description={text('复制专属链接给好友。好友注册并充值后，返佣会先进入待到账，成熟后可划转到点数余额或申请提现。', 'Share your invite link. Rewards from friends’ paid top-ups become available after the pending period, then can be transferred to credits or withdrawn.')}
        action={<Button variant="outline" disabled={loading} onClick={() => void load()}><RefreshCw />{text('刷新', 'Refresh')}</Button>}
      />

      <PixPanel>
        <div className="overflow-hidden rounded-xl border border-border bg-[hsl(var(--pix-navy))] text-white shadow-[0_24px_80px_-46px_rgba(0,0,0,.78)] dark:border-white/10">
          <div className="relative grid gap-6 p-5 sm:p-6">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_0%,rgba(80,220,182,.28),transparent_34%),radial-gradient(circle_at_78%_6%,rgba(74,144,245,.24),transparent_28%),linear-gradient(120deg,rgba(18,119,117,.66),rgba(12,55,71,.82))]" />
            <div className="relative flex flex-wrap items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="grid h-10 w-10 place-items-center rounded-full bg-emerald-400/18 text-emerald-200 ring-1 ring-emerald-200/20"><Gift className="h-5 w-5" /></div>
                <div>
                  <h2 className="text-lg font-semibold">{text('收益统计', 'Reward stats')}</h2>
                  <p className="text-sm text-white/68">{text(`当前返佣比例 ${rate}%`, `Current commission rate ${rate}%`)}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="secondary" disabled={working || available <= 0} onClick={() => void withdrawRewards()}><Banknote />{text('提现', 'Withdraw')}</Button>
                <Button size="sm" disabled={working || available <= 0} onClick={() => void transferRewards()}><ArrowRightLeft />{text('划转到余额', 'Transfer to credits')}</Button>
              </div>
            </div>
            <div className="relative grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <RewardMetric icon={<Clock3 />} label={text('待到账收益', 'Pending rewards')} value={money(summary?.pending_cents ?? 0, primaryCurrency)} />
              <RewardMetric icon={<WalletCards />} label={text('可用收益', 'Available rewards')} value={money(available, primaryCurrency)} />
              <RewardMetric icon={<Banknote />} label={text('总收益', 'Total rewards')} value={money(summary?.total_reward_cents ?? 0, primaryCurrency)} />
              <RewardMetric icon={<Users />} label={text('邀请人数', 'Invited users')} value={summary?.invited_count ?? 0} />
            </div>
            <div className="relative grid gap-2 rounded-lg bg-black/24 p-2 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center">
              <span className="px-2 text-xs font-semibold text-white/58">{text('邀请链接', 'Invite link')}</span>
              <code className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap rounded-md bg-white/10 px-3 py-2 text-sm text-white">{summary?.invite_url ?? text('正在生成邀请链接…', 'Generating invite link…')}</code>
              <Button size="sm" disabled={!summary?.invite_url} onClick={() => void copyInviteLink()}><Copy />{text('复制', 'Copy')}</Button>
            </div>
          </div>
        </div>

        <div className="mt-4 grid gap-3">
          {notice && <Alert variant="success">{notice}</Alert>}
          {error && <Alert variant="destructive">{error}</Alert>}
          {!summary?.enabled && <Alert variant="warning">{text('邀请奖励当前已关闭，已有收益仍可查看。', 'Referral rewards are currently disabled; existing rewards remain visible.')}</Alert>}
        </div>
      </PixPanel>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <PixPanel>
          <div className="flex flex-wrap gap-2 border-b border-border pb-3 dark:border-white/10">
            {REWARD_TABS.map((item) => (
              <Button key={item} type="button" size="sm" variant={tab === item ? 'default' : 'ghost'} onClick={() => setTab(item)}>
                {tabLabel(item, text)}
                <Badge variant="secondary">{tabCount[item]}</Badge>
              </Button>
            ))}
          </div>
          <div className="mt-4">
            {loading ? <RewardEmpty title={text('正在同步邀请奖励…', 'Syncing referral rewards…')} /> : null}
            {!loading && tab === 'invites' && <InviteRows rows={summary?.invites ?? []} onCopy={copyInviteLink} />}
            {!loading && tab === 'rewards' && <RewardRows rows={summary?.rewards ?? []} />}
            {!loading && tab === 'settlements' && <SettlementRows rows={summary?.settlements ?? []} />}
          </div>
        </PixPanel>

        <PixPanel eyebrow={text('奖励说明', 'Reward rules')} title={text('返佣如何到账', 'How rewards settle')}>
          <ul className="grid gap-3 text-sm leading-6 text-muted-foreground">
            <RuleItem>{text(`当前返佣比例：${rate}%`, `Current commission rate: ${rate}%`)}</RuleItem>
            <RuleItem>{text('邀请好友注册，好友充值后您可获得相应奖励。', 'Invite friends to register; you earn rewards after their paid top-ups.')}</RuleItem>
            <RuleItem>{text(`好友充值后返利将进入待到账，${summary?.pending_days ?? 30} 天后自动转入可用收益。`, `Rewards stay pending and become available after ${summary?.pending_days ?? 30} days.`)}</RuleItem>
            <RuleItem>{text('通过划转功能将奖励兑换到您的账户余额中。', 'Use transfer to convert rewards into account credits.')}</RuleItem>
            <RuleItem>{text('提现申请会进入人工处理流程，处理完成后可在记录中追踪。', 'Withdrawal requests enter manual review and can be tracked in records.')}</RuleItem>
          </ul>
        </PixPanel>
      </div>
    </div>
  )
}

function RewardMetric({ icon, label, value }: { icon: ReactNode; label: ReactNode; value: ReactNode }) {
  return (
    <div className="rounded-lg bg-white/8 px-4 py-4 ring-1 ring-white/10">
      <div className="flex items-center gap-2 text-white/68 [&_svg]:h-4 [&_svg]:w-4">{icon}<span className="text-xs font-semibold">{label}</span></div>
      <p className="mt-3 text-3xl font-bold tabular-nums tracking-tight">{value}</p>
    </div>
  )
}

function InviteRows({ rows, onCopy }: { rows: ReferralInvite[]; onCopy: () => void }) {
  const { text } = useI18n()
  if (!rows.length) return <RewardEmpty title={text('暂无邀请记录', 'No invites yet')} action={<Button size="sm" onClick={() => void onCopy()}><Copy />{text('复制邀请链接，邀请好友', 'Copy invite link')}</Button>} />
  return <div className="grid gap-2">{rows.map((row) => <RecordRow key={row.id} title={row.referred_user_display_name || row.referred_user_email} meta={row.referred_user_email} right={formatDateTime(row.created_at)} />)}</div>
}

function RewardRows({ rows }: { rows: ReferralReward[] }) {
  const { text } = useI18n()
  if (!rows.length) return <RewardEmpty title={text('暂无返佣明细', 'No reward records yet')} />
  return <div className="grid gap-2">{rows.map((row) => <RecordRow key={row.id} title={money(row.amount_cents, row.currency)} meta={text(`订单 #${row.order_id} · ${rewardStatus(row.status, text)} · ${row.referred_user_email}`, `Order #${row.order_id} · ${rewardStatus(row.status, text)} · ${row.referred_user_email}`)} right={formatDateTime(row.created_at)} />)}</div>
}

function SettlementRows({ rows }: { rows: ReferralSettlement[] }) {
  const { text } = useI18n()
  if (!rows.length) return <RewardEmpty title={text('暂无提现或划转记录', 'No transfer or withdrawal records yet')} />
  return <div className="grid gap-2">{rows.map((row) => <RecordRow key={row.id} title={settlementTitle(row, text)} meta={`${settlementStatus(row.status, text)} · ${row.note || text('无备注', 'No note')}`} right={formatDateTime(row.created_at)} />)}</div>
}

function RecordRow({ title, meta, right }: { title: ReactNode; meta: ReactNode; right: ReactNode }) {
  return (
    <div className="grid gap-2 rounded-lg border border-border bg-card px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center dark:border-white/10 dark:bg-white/5">
      <div className="min-w-0"><p className="truncate font-semibold">{title}</p><p className="mt-1 truncate text-sm text-muted-foreground">{meta}</p></div>
      <p className="text-xs text-muted-foreground">{right}</p>
    </div>
  )
}

function RewardEmpty({ title, action }: { title: ReactNode; action?: ReactNode }) {
  return <div className="grid min-h-56 place-items-center gap-3 rounded-lg border border-dashed border-border bg-muted/28 p-8 text-center dark:border-white/10 dark:bg-white/5"><Gift className="h-12 w-12 text-muted-foreground" /><p className="text-sm text-muted-foreground">{title}</p>{action}</div>
}

function RuleItem({ children }: { children: ReactNode }) {
  return <li className="grid grid-cols-[10px_minmax(0,1fr)] gap-3"><span className="mt-2 h-2 w-2 rounded-full bg-emerald-500" />{children}</li>
}

function tabLabel(tab: RewardTab, text: (zh: string, en: string) => string) {
  if (tab === 'invites') return text('邀请记录', 'Invites')
  if (tab === 'rewards') return text('返佣明细', 'Rewards')
  return text('提现记录', 'Settlements')
}

function rewardStatus(status: string, text: (zh: string, en: string) => string) {
  if (status === 'pending') return text('待到账', 'Pending')
  if (status === 'available') return text('可用', 'Available')
  if (status === 'settled') return text('已结算', 'Settled')
  return status
}

function settlementStatus(status: string, text: (zh: string, en: string) => string) {
  if (status === 'pending') return text('待处理', 'Pending')
  if (status === 'completed') return text('已完成', 'Completed')
  return status
}

function settlementTitle(row: ReferralSettlement, text: (zh: string, en: string) => string) {
  if (row.type === 'transfer') return text(`划转 ${row.credits} 点`, `Transferred ${row.credits} credits`)
  return text(`提现 ${money(row.amount_cents, row.currency)}`, `Withdrawal ${money(row.amount_cents, row.currency)}`)
}

function money(cents: number, currency = 'cny') {
  const value = (cents / 100).toFixed(2)
  const clean = currency.toLowerCase()
  if (clean === 'cny') return `¥${value}`
  if (clean === 'usd') return `$${value}`
  return `${clean.toUpperCase()} ${value}`
}
