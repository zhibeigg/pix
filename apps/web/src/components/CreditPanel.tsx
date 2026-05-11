import { QRCodeSVG } from 'qrcode.react'
import { Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Card, CardContent, Chip, Divider, Stack, Typography } from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { notionTokens } from '../theme'
import type { CreditBalance, CreditPackage, CreditTransaction, PaymentCheckout, PaymentOrder } from '../types'

type CreditPanelProps = {
  balance: CreditBalance | null
  transactions: CreditTransaction[]
  packages: CreditPackage[]
  orders: PaymentOrder[]
  checkout: PaymentCheckout | null
  isAdmin: boolean
  onRefresh: () => void
  onCreateOrder: (packageKey: string) => Promise<void>
  onCheckout: (packageKey: string, provider: string) => Promise<void>
  onMockPayOrder: (orderId: number) => Promise<void>
}

export function CreditPanel({ balance, transactions, packages, orders, checkout, isAdmin, onRefresh, onCreateOrder, onCheckout, onMockPayOrder }: CreditPanelProps) {
  async function copyWechatLink() {
    if (!checkout?.code_url) return
    await navigator.clipboard.writeText(checkout.code_url)
  }

  return (
    <Card variant="outlined" sx={{ bgcolor: notionTokens.canvas }}>
      <CardContent>
        <Stack spacing={3}>
          <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', gap: 2 }}>
            <Box>
              <Typography variant="overline" color="primary.main" sx={{ fontWeight: 600 }}>Credits</Typography>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>点数账户</Typography>
            </Box>
            <Button variant="outlined" onClick={onRefresh}>刷新</Button>
          </Stack>

          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 1.25 }}>
            <Metric label="可用" value={balance?.available_credits ?? '—'} />
            <Metric label="冻结" value={balance?.reserved_credits ?? '—'} />
            <Metric label="累计充值" value={balance?.total_recharged ?? '—'} />
            <Metric label="累计消费" value={balance?.total_consumed ?? '—'} />
          </Box>

          <Stack spacing={1.5}>
            {packages.map((item) => (
              <Card variant="outlined" key={item.key} sx={{ bgcolor: notionTokens.tintCream }}>
                <CardContent>
                  <Stack direction={{ xs: 'column', md: 'row' }} sx={{ justifyContent: 'space-between', gap: 2, alignItems: { xs: 'stretch', md: 'center' } }}>
                    <Box>
                      <Typography sx={{ fontWeight: 600 }}>{item.name}</Typography>
                      <Typography color="text.secondary" variant="body2">{item.credits} credits · ¥{(item.amount_cents / 100).toFixed(2)}</Typography>
                    </Box>
                    <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
                      <Button variant="contained" color="primary" onClick={() => onCheckout(item.key, 'alipay')}>支付宝</Button>
                      <Button variant="outlined" onClick={() => onCheckout(item.key, 'wechat')}>微信</Button>
                      {isAdmin && <Button variant="text" onClick={() => onCreateOrder(item.key)}>Mock</Button>}
                    </Stack>
                  </Stack>
                </CardContent>
              </Card>
            ))}
          </Stack>

          {checkout?.code_url && (
            <Card variant="outlined" role="img" aria-label={`微信支付二维码，订单 ${checkout.order.id}`} sx={{ bgcolor: notionTokens.tintMint }}>
              <CardContent>
                <Stack spacing={1.5} sx={{ alignItems: 'center' }}>
                  <Typography sx={{ fontWeight: 600 }}>微信扫码支付订单 #{checkout.order.id}</Typography>
                  <QRCodeSVG value={checkout.code_url} size={180} />
                  <Typography color="text.secondary" variant="body2">支付完成后点击刷新查看到账状态。</Typography>
                  <Button variant="outlined" size="small" onClick={copyWechatLink}>复制微信支付链接</Button>
                  <Accordion sx={{ width: '100%' }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>查看备用链接</AccordionSummary>
                    <AccordionDetails><Box component="code" sx={{ display: 'block', maxWidth: '100%', overflowWrap: 'anywhere', color: 'info.light', fontSize: 12 }}>{checkout.code_url}</Box></AccordionDetails>
                  </Accordion>
                </Stack>
              </CardContent>
            </Card>
          )}
          {checkout?.payment_url && <Alert severity="info">支付宝付款页已在新窗口打开，支付完成后点击刷新。</Alert>}

          <Accordion defaultExpanded={orders.length > 0}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>充值订单</AccordionSummary>
            <AccordionDetails>
              <Stack spacing={1}>
                {orders.length === 0 ? <Typography color="text.secondary">暂无充值订单。</Typography> : orders.map((order) => (
                  <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ justifyContent: 'space-between', gap: 1 }} key={order.id}>
                    <Box>
                      <Typography sx={{ fontWeight: 850 }}>订单 #{order.id}</Typography>
                      <Typography color="text.secondary" variant="body2">{order.credits} credits · ¥{(order.amount_cents / 100).toFixed(2)}</Typography>
                    </Box>
                    <Stack direction="row" sx={{ gap: 1, alignItems: 'center' }}>
                      <Chip size="small" label={order.status} color={order.status === 'paid' ? 'success' : 'warning'} />
                      {isAdmin && order.status !== 'paid' && <Button size="small" onClick={() => onMockPayOrder(order.id)}>模拟支付</Button>}
                    </Stack>
                  </Stack>
                ))}
              </Stack>
            </AccordionDetails>
          </Accordion>

          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>点数流水</AccordionSummary>
            <AccordionDetails>
              <Stack spacing={1} divider={<Divider flexItem />}>
                {transactions.length === 0 ? <Typography color="text.secondary">暂无流水。管理员可先给账户加点。</Typography> : transactions.map((tx) => (
                  <Stack direction="row" sx={{ justifyContent: 'space-between', gap: 2 }} key={tx.id}>
                    <Box>
                      <Typography sx={{ fontWeight: 850 }}>{tx.type}</Typography>
                      <Typography color="text.secondary" variant="body2">{tx.note || '—'}</Typography>
                    </Box>
                    <Typography color={tx.amount >= 0 ? 'success.main' : 'error.main'} sx={{ fontWeight: 600 }}>{tx.amount > 0 ? `+${tx.amount}` : tx.amount}</Typography>
                  </Stack>
                ))}
              </Stack>
            </AccordionDetails>
          </Accordion>
        </Stack>
      </CardContent>
    </Card>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <Box sx={{ bgcolor: notionTokens.tintLavender, border: 1, borderColor: 'divider', borderRadius: 1.5, p: 1.5, fontVariantNumeric: 'tabular-nums' }}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography variant="h5" sx={{ fontWeight: 600 }}>{value}</Typography>
    </Box>
  )
}
