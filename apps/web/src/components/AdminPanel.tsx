import { FormEvent, useState } from 'react'
import { Box, Button, Card, CardContent, Checkbox, FormControlLabel, MenuItem, Stack, Tab, Tabs, TextField, Typography } from '@mui/material'
import type { AdminDashboard, PricingRule, SystemSetting, User } from '../types'

type AdminPanelProps = {
  dashboard: AdminDashboard | null
  users: User[]
  pricing: PricingRule[]
  settings: SystemSetting[]
  onRefresh: () => void
  onAdjustCredits: (userId: number, amount: number, note: string) => Promise<void>
  onUpdatePricing: (key: string, priceCredits: number, enabled: boolean) => Promise<void>
  onUpdateSetting: (key: string, value: string) => Promise<void>
}

type AdminTab = 'dashboard' | 'users' | 'pricing' | 'settings'

export function AdminPanel({ dashboard, users, pricing, settings, onRefresh, onAdjustCredits, onUpdatePricing, onUpdateSetting }: AdminPanelProps) {
  const [tab, setTab] = useState<AdminTab>('dashboard')
  const [selectedUser, setSelectedUser] = useState<number>(0)
  const [amount, setAmount] = useState(100)
  const [note, setNote] = useState('seed credits')

  async function submitAdjust(event: FormEvent) {
    event.preventDefault()
    if (!selectedUser) return
    await onAdjustCredits(selectedUser, amount, note)
  }

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack spacing={3}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 2 }}>
            <Box>
              <Typography variant="overline" color="primary.main" sx={{ fontWeight: 900 }}>Admin</Typography>
              <Typography variant="h4" sx={{ fontWeight: 950 }}>运营控制台</Typography>
            </Box>
            <Button variant="outlined" onClick={onRefresh}>刷新</Button>
          </Stack>

          <Tabs value={tab} variant="scrollable" scrollButtons="auto" onChange={(_, value: AdminTab) => setTab(value)} aria-label="管理后台栏目">
            <Tab value="dashboard" label="概览" />
            <Tab value="users" label="用户与点数" />
            <Tab value="pricing" label="价格规则" />
            <Tab value="settings" label="运营保护" />
          </Tabs>

          {tab === 'dashboard' && dashboard && (
            <Box className="metric-grid">
              <Metric label="今日任务" value={dashboard.jobs_today} />
              <Metric label="成功 / 失败" value={`${dashboard.succeeded_today} / ${dashboard.failed_today}`} />
              <Metric label="排队 / 运行" value={`${dashboard.pending_jobs} / ${dashboard.running_jobs}`} />
              <Metric label="今日充值" value={dashboard.credits_recharged_today} />
              <Metric label="今日消费" value={dashboard.credits_consumed_today} />
              <Metric label="今日上传" value={dashboard.uploads_today} />
              <Metric label="总用户" value={dashboard.total_users} />
              <Metric label="失败率" value={`${Math.round(dashboard.failure_rate * 100)}%`} />
            </Box>
          )}

          {tab === 'users' && (
            <Stack component="form" spacing={2} sx={{ maxWidth: 520 }} onSubmit={submitAdjust}>
              <Typography variant="h6" sx={{ fontWeight: 900 }}>手动加点</Typography>
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
              <Typography variant="h6" sx={{ fontWeight: 900 }}>价格规则</Typography>
              {pricing.map((rule) => <PricingRow rule={rule} onUpdate={onUpdatePricing} key={rule.key} />)}
            </Stack>
          )}

          {tab === 'settings' && (
            <Stack spacing={1.5}>
              <Typography variant="h6" sx={{ fontWeight: 900 }}>运营保护</Typography>
              {settings.map((setting) => <SettingRow setting={setting} onUpdate={onUpdateSetting} key={setting.key} />)}
            </Stack>
          )}
        </Stack>
      </CardContent>
    </Card>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <Box className="metric">
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography variant="h5" sx={{ fontWeight: 950 }}>{value}</Typography>
    </Box>
  )
}

function SettingRow({ setting, onUpdate }: { setting: SystemSetting; onUpdate: (key: string, value: string) => Promise<void> }) {
  const [value, setValue] = useState(setting.value)
  const isBoolean = setting.key === 'generation_enabled'
  const isTextArea = setting.key === 'blocked_prompt_terms'
  return (
    <Card variant="outlined" sx={{ bgcolor: 'background.default' }}>
      <CardContent>
        <Stack direction={{ xs: 'column', md: 'row' }} sx={{ gap: 2, alignItems: { md: 'center' } }}>
          <Box sx={{ flex: 1 }}>
            <Typography sx={{ fontWeight: 900 }}>{settingLabel(setting.key)}</Typography>
            <Typography variant="caption" color="text.secondary">{setting.key}</Typography>
          </Box>
          {isBoolean ? (
            <FormControlLabel control={<Checkbox checked={value === 'true'} onChange={(event) => setValue(event.target.checked ? 'true' : 'false')} />} label="启用" />
          ) : (
            <TextField sx={{ minWidth: { md: 280 } }} multiline={isTextArea} minRows={isTextArea ? 3 : undefined} type={isTextArea ? 'text' : 'number'} value={value} onChange={(event) => setValue(event.target.value)} />
          )}
          <Button variant="outlined" onClick={() => onUpdate(setting.key, value)}>保存</Button>
        </Stack>
      </CardContent>
    </Card>
  )
}

function settingLabel(key: string) {
  const labels: Record<string, string> = {
    generation_enabled: '生成总开关',
    max_pending_jobs_per_user: '每用户排队/运行上限',
    daily_job_limit_per_user: '每用户每日任务上限',
    blocked_prompt_terms: 'Prompt 禁词',
    max_uploads_per_user_per_day: '每用户每日上传上限',
  }
  return labels[key] ?? key
}

function PricingRow({ rule, onUpdate }: { rule: PricingRule; onUpdate: (key: string, priceCredits: number, enabled: boolean) => Promise<void> }) {
  const [price, setPrice] = useState(rule.price_credits)
  const [enabled, setEnabled] = useState(rule.enabled)
  return (
    <Card variant="outlined" sx={{ bgcolor: 'background.default' }}>
      <CardContent>
        <Stack direction={{ xs: 'column', md: 'row' }} sx={{ gap: 2, alignItems: { md: 'center' } }}>
          <Box sx={{ flex: 1 }}>
            <Typography sx={{ fontWeight: 900 }}>{rule.key}</Typography>
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
