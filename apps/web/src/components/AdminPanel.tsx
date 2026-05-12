import { FormEvent, useMemo, useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Checkbox, Chip, FormControlLabel, MenuItem, Stack, Tab, Tabs, TextField, Typography } from '@mui/material'
import { notionTokens } from '../theme'
import type { AdminDashboard, CreditPackage, PricingRule, SystemSetting, User } from '../types'

type AdminPanelProps = {
  dashboard: AdminDashboard | null
  users: User[]
  pricing: PricingRule[]
  packages: CreditPackage[]
  settings: SystemSetting[]
  onRefresh: () => void
  onAdjustCredits: (userId: number, amount: number, note: string) => Promise<void>
  onUpdatePricing: (key: string, priceCredits: number, enabled: boolean) => Promise<void>
  onCreatePackage: (payload: CreditPackage) => Promise<void>
  onUpdatePackage: (key: string, payload: Omit<CreditPackage, 'key'>) => Promise<void>
  onUpdateSetting: (key: string, value: string, clear?: boolean) => Promise<void>
  onTestEmail: (email: string) => Promise<void>
}

type AdminTab = 'dashboard' | 'users' | 'pricing' | 'packages' | string

const settingTabs = ['运营保护', '邮件验证码', '模型与 API', '素材默认值', '支付与站点', '存储 / 队列 / 安全']

export function AdminPanel({ dashboard, users, pricing, packages, settings, onRefresh, onAdjustCredits, onUpdatePricing, onCreatePackage, onUpdatePackage, onUpdateSetting, onTestEmail }: AdminPanelProps) {
  const [tab, setTab] = useState<AdminTab>('dashboard')
  const [selectedUser, setSelectedUser] = useState<number>(0)
  const [amount, setAmount] = useState(100)
  const [note, setNote] = useState('运营补点')
  const groups = useMemo(() => groupSettings(settings), [settings])

  async function submitAdjust(event: FormEvent) {
    event.preventDefault()
    if (!selectedUser) return
    await onAdjustCredits(selectedUser, amount, note)
  }

  const settingGroup = groups[tab]

  return (
    <Card variant="outlined" sx={{ bgcolor: notionTokens.canvas }}>
      <CardContent>
        <Stack spacing={3}>
          <Stack direction={{ xs: 'column', md: 'row' }} sx={{ justifyContent: 'space-between', alignItems: { xs: 'stretch', md: 'center' }, gap: 2 }}>
            <Box>
              <Typography variant="overline" color="primary.main" sx={{ fontWeight: 700 }}>Control Room</Typography>
              <Typography variant="h4" sx={{ fontWeight: 700 }}>管理后台</Typography>
              <Typography color="text.secondary" sx={{ mt: .5 }}>配置站点、模型、邮件、套餐和运营保护。高风险环境项只显示状态。</Typography>
            </Box>
            <Button variant="outlined" onClick={onRefresh}>刷新</Button>
          </Stack>

          <Tabs value={tab} variant="scrollable" scrollButtons="auto" onChange={(_, value: AdminTab) => setTab(value)} aria-label="管理后台栏目">
            <Tab value="dashboard" label="概览" />
            <Tab value="users" label="用户与点数" />
            <Tab value="pricing" label="价格规则" />
            <Tab value="packages" label="充值套餐" />
            {settingTabs.map((item) => <Tab key={item} value={item} label={item} />)}
          </Tabs>

          {tab === 'dashboard' && dashboard && <DashboardGrid dashboard={dashboard} />}

          {tab === 'users' && (
            <Stack component="form" spacing={2} sx={{ maxWidth: 560 }} onSubmit={submitAdjust}>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>手动加点</Typography>
              <TextField select label="用户" value={selectedUser} onChange={(event) => setSelectedUser(Number(event.target.value))}>
                <MenuItem value={0}>选择用户</MenuItem>
                {users.map((user) => <MenuItem value={user.id} key={user.id}>{user.email} · {user.role}</MenuItem>)}
              </TextField>
              <TextField label="点数变化" type="number" value={amount} onChange={(event) => setAmount(Number(event.target.value))} />
              <TextField label="备注" value={note} onChange={(event) => setNote(event.target.value)} />
              <Button type="submit" variant="contained">调整点数</Button>
            </Stack>
          )}

          {tab === 'pricing' && (
            <Stack spacing={1.5}>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>价格规则</Typography>
              {pricing.map((rule) => <PricingRow rule={rule} onUpdate={onUpdatePricing} key={rule.key} />)}
            </Stack>
          )}

          {tab === 'packages' && <PackageEditor packages={packages} onCreate={onCreatePackage} onUpdate={onUpdatePackage} />}

          {settingGroup && (
            <Stack spacing={1.5}>
              <Stack direction={{ xs: 'column', md: 'row' }} sx={{ justifyContent: 'space-between', gap: 1.5, alignItems: { md: 'center' } }}>
                <Box>
                  <Typography variant="h6" sx={{ fontWeight: 700 }}>{tab}</Typography>
                  <Typography color="text.secondary">保存后只影响新请求/新任务；带“需重启”的项目请重启服务或 worker。</Typography>
                </Box>
                {tab === '邮件验证码' && <EmailTestBox onTest={onTestEmail} />}
              </Stack>
              {settingGroup.map((setting) => <SettingRow setting={setting} onUpdate={onUpdateSetting} key={setting.key} />)}
            </Stack>
          )}
        </Stack>
      </CardContent>
    </Card>
  )
}

function groupSettings(settings: SystemSetting[]) {
  return settings.reduce<Record<string, SystemSetting[]>>((acc, setting) => {
    const category = setting.category || '其他'
    acc[category] = acc[category] || []
    acc[category].push(setting)
    return acc
  }, {})
}

function DashboardGrid({ dashboard }: { dashboard: AdminDashboard }) {
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: 'repeat(4, 1fr)' }, gap: 1.25 }}>
      <Metric label="今日任务" value={dashboard.jobs_today} />
      <Metric label="成功 / 失败" value={`${dashboard.succeeded_today} / ${dashboard.failed_today}`} />
      <Metric label="排队 / 运行" value={`${dashboard.pending_jobs} / ${dashboard.running_jobs}`} />
      <Metric label="今日充值" value={dashboard.credits_recharged_today} />
      <Metric label="今日消费" value={dashboard.credits_consumed_today} />
      <Metric label="今日上传" value={dashboard.uploads_today} />
      <Metric label="总用户" value={dashboard.total_users} />
      <Metric label="失败率" value={`${Math.round(dashboard.failure_rate * 100)}%`} />
    </Box>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <Box sx={{ bgcolor: notionTokens.tintSky, border: 1, borderColor: 'divider', borderRadius: 1.5, p: 1.5, fontVariantNumeric: 'tabular-nums' }}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography variant="h5" sx={{ fontWeight: 700 }}>{value}</Typography>
    </Box>
  )
}

function EmailTestBox({ onTest }: { onTest: (email: string) => Promise<void> }) {
  const [email, setEmail] = useState('admin@example.com')
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} component="form" onSubmit={(event) => { event.preventDefault(); void onTest(email) }}>
      <TextField size="small" label="测试邮箱" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
      <Button type="submit" variant="outlined">发送测试</Button>
    </Stack>
  )
}

function SettingRow({ setting, onUpdate }: { setting: SystemSetting; onUpdate: (key: string, value: string, clear?: boolean) => Promise<void> }) {
  const [value, setValue] = useState(setting.value)
  const [clearSecret, setClearSecret] = useState(false)
  const isBoolean = setting.type === 'boolean'
  const isTextArea = setting.type === 'textarea'
  const isSecret = setting.type === 'secret'
  const disabled = !setting.editable

  const helper = [setting.help, setting.env_var ? `环境变量：${setting.env_var}` : '', setting.restart_required ? '保存后需重启服务或 worker 生效。' : ''].filter(Boolean).join(' · ')

  return (
    <Card variant="outlined" sx={{ bgcolor: disabled ? notionTokens.tintGray : notionTokens.tintCream }}>
      <CardContent>
        <Stack direction={{ xs: 'column', lg: 'row' }} sx={{ gap: 2, alignItems: { lg: 'center' } }}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
              <Typography sx={{ fontWeight: 700 }}>{setting.label || setting.key}</Typography>
              {setting.restart_required && <Chip size="small" label="需重启" sx={{ bgcolor: notionTokens.tintYellowBold, borderRadius: 1 }} />}
              {setting.secret && <Chip size="small" label="Secret" sx={{ bgcolor: notionTokens.tintLavender, color: notionTokens.brandPurple800, borderRadius: 1 }} />}
              {!setting.editable && <Chip size="small" label="只读" sx={{ bgcolor: notionTokens.canvas, borderRadius: 1 }} />}
            </Stack>
            <Typography variant="caption" color="text.secondary">{setting.key}</Typography>
            {helper && <Typography variant="body2" color="text.secondary" sx={{ mt: .6 }}>{helper}</Typography>}
          </Box>

          {setting.type === 'status' ? (
            <Typography sx={{ minWidth: 180, fontWeight: 700 }}>{setting.masked ? '已配置' : setting.value || '未配置'}</Typography>
          ) : isBoolean ? (
            <FormControlLabel disabled={disabled} control={<Checkbox checked={value === 'true'} onChange={(event) => setValue(event.target.checked ? 'true' : 'false')} />} label="启用" />
          ) : setting.type === 'select' ? (
            <TextField select disabled={disabled} sx={{ minWidth: { lg: 260 } }} value={value} onChange={(event) => setValue(event.target.value)}>
              {setting.options.map((option) => <MenuItem key={option} value={option}>{option}</MenuItem>)}
            </TextField>
          ) : (
            <Stack spacing={.8} sx={{ minWidth: { lg: 300 } }}>
              <TextField disabled={disabled || clearSecret} multiline={isTextArea} minRows={isTextArea ? 3 : undefined} type={isSecret ? 'password' : setting.type === 'number' ? 'number' : 'text'} placeholder={isSecret && setting.masked ? '留空保持当前密钥' : undefined} value={value} onChange={(event) => setValue(event.target.value)} />
              {isSecret && <FormControlLabel control={<Checkbox checked={clearSecret} onChange={(event) => setClearSecret(event.target.checked)} />} label="清空当前值" />}
            </Stack>
          )}

          {setting.editable && <Button variant="outlined" onClick={() => onUpdate(setting.key, clearSecret ? '' : value, clearSecret)}>保存</Button>}
        </Stack>
      </CardContent>
    </Card>
  )
}

function PricingRow({ rule, onUpdate }: { rule: PricingRule; onUpdate: (key: string, priceCredits: number, enabled: boolean) => Promise<void> }) {
  const [price, setPrice] = useState(rule.price_credits)
  const [enabled, setEnabled] = useState(rule.enabled)
  return (
    <Card variant="outlined" sx={{ bgcolor: notionTokens.tintCream }}>
      <CardContent>
        <Stack direction={{ xs: 'column', md: 'row' }} sx={{ gap: 2, alignItems: { md: 'center' } }}>
          <Box sx={{ flex: 1 }}>
            <Typography sx={{ fontWeight: 700 }}>{rule.key}</Typography>
            <Typography variant="caption" color="text.secondary">{rule.enabled ? '启用' : '停用'}</Typography>
          </Box>
          <TextField label="价格" type="number" value={price} onChange={(event) => setPrice(Number(event.target.value))} sx={{ width: { md: 140 } }} />
          <FormControlLabel control={<Checkbox checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />} label="启用" />
          <Button variant="outlined" onClick={() => onUpdate(rule.key, price, enabled)}>保存</Button>
        </Stack>
      </CardContent>
    </Card>
  )
}

function PackageEditor({ packages, onCreate, onUpdate }: { packages: CreditPackage[]; onCreate: (payload: CreditPackage) => Promise<void>; onUpdate: (key: string, payload: Omit<CreditPackage, 'key'>) => Promise<void> }) {
  const [draft, setDraft] = useState<CreditPackage>({ key: 'custom', name: 'Custom', credits: 100, amount_cents: 990, currency: 'cny', enabled: true, sort_order: 40 })
  return (
    <Stack spacing={1.5}>
      <Typography variant="h6" sx={{ fontWeight: 700 }}>充值套餐</Typography>
      <Alert severity="info">历史订单会引用套餐 ID，因此这里不提供删除；不需要的套餐请停用。</Alert>
      {packages.map((item) => <PackageRow key={item.key} item={item} onUpdate={onUpdate} />)}
      <Card variant="outlined" sx={{ bgcolor: notionTokens.tintMint }}>
        <CardContent>
          <Stack direction={{ xs: 'column', lg: 'row' }} sx={{ gap: 1.2, alignItems: { lg: 'center' } }}>
            <TextField label="key" value={draft.key} onChange={(event) => setDraft({ ...draft, key: event.target.value })} />
            <TextField label="名称" value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
            <TextField label="点数" type="number" value={draft.credits} onChange={(event) => setDraft({ ...draft, credits: Number(event.target.value) })} />
            <TextField label="金额（分）" type="number" value={draft.amount_cents} onChange={(event) => setDraft({ ...draft, amount_cents: Number(event.target.value) })} />
            <TextField label="币种" value={draft.currency} onChange={(event) => setDraft({ ...draft, currency: event.target.value })} />
            <TextField label="排序" type="number" value={draft.sort_order} onChange={(event) => setDraft({ ...draft, sort_order: Number(event.target.value) })} />
            <FormControlLabel control={<Checkbox checked={draft.enabled} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} />} label="启用" />
            <Button variant="contained" onClick={() => onCreate(draft)}>新增</Button>
          </Stack>
        </CardContent>
      </Card>
    </Stack>
  )
}

function PackageRow({ item, onUpdate }: { item: CreditPackage; onUpdate: (key: string, payload: Omit<CreditPackage, 'key'>) => Promise<void> }) {
  const [name, setName] = useState(item.name)
  const [credits, setCredits] = useState(item.credits)
  const [amount, setAmount] = useState(item.amount_cents)
  const [currency, setCurrency] = useState(item.currency)
  const [enabled, setEnabled] = useState(item.enabled)
  const [sortOrder, setSortOrder] = useState(item.sort_order)
  return (
    <Card variant="outlined" sx={{ bgcolor: notionTokens.tintCream }}>
      <CardContent>
        <Stack direction={{ xs: 'column', lg: 'row' }} sx={{ gap: 1.2, alignItems: { lg: 'center' } }}>
          <Box sx={{ minWidth: 120 }}>
            <Typography sx={{ fontWeight: 700 }}>{item.key}</Typography>
            <Typography variant="caption" color="text.secondary">{item.enabled ? '公开展示' : '已停用'}</Typography>
          </Box>
          <TextField label="名称" value={name} onChange={(event) => setName(event.target.value)} />
          <TextField label="点数" type="number" value={credits} onChange={(event) => setCredits(Number(event.target.value))} />
          <TextField label="金额（分）" type="number" value={amount} onChange={(event) => setAmount(Number(event.target.value))} />
          <TextField label="币种" value={currency} onChange={(event) => setCurrency(event.target.value)} />
          <TextField label="排序" type="number" value={sortOrder} onChange={(event) => setSortOrder(Number(event.target.value))} />
          <FormControlLabel control={<Checkbox checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />} label="启用" />
          <Button variant="outlined" onClick={() => onUpdate(item.key, { name, credits, amount_cents: amount, currency, enabled, sort_order: sortOrder })}>保存</Button>
        </Stack>
      </CardContent>
    </Card>
  )
}
