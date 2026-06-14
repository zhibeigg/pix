# App.tsx 业务域拆分设计（前端重构 · 批次 4 第二层）

> 状态：**待执行**（建议独立会话 + 先补关键路径测试）
> 前置：批次 4 第一层已完成（提取 `useToast` / `useHashRoute` / `useReferralCode`，App.tsx ≈ 990 行）。

## 1. 背景与目标

`App.tsx` 仍集中管理全部**业务状态**（约 30 个 `useState`）+ **业务操作**（约 30 个函数）+ **数据获取**（`refreshCore` 全量刷新 + 3 秒 `poll`）。第一层已抽走横切关注点（toast / 路由 / 邀请码）。

第二层目标：把业务**按域**拆成自定义 hooks，`App.tsx` 退化为「组装层」（调用 hooks + 渲染）。

## 2. 为什么必须先有测试网

这一步触及**最核心、相互依赖最深的数据流**，而项目当前**没有前端测试**。`tsc` 只能保证类型正确，抓不到运行时回归：

- **closure 过期**：操作 hook 闭包捕获的 `token` / state 若依赖项写错，会用到旧值
- **refresh 时序**：写操作后 `refreshCore` 的调用时机 / 顺序错乱
- **依赖遗漏**：`useCallback` 依赖数组漏项导致 stale

**执行前置**：用 vitest + @testing-library/react 为以下关键路径加测试（至少 smoke）：
1. 登录 → `refreshCore` 拉数据 → 渲染
2. `createJob` → 提交 → 跳转画廊 → 刷新
3. 轮询签名比较（稳定期不 setState）
4. 支付返回 hash → 刷新订单
5. 登出 → 清空所有 state

## 3. 目标架构

```
App({...themeProps})
├─ useI18n() / useConfirm()                         // 既有
├─ useToast(text)                                   // 第一层 ✓
├─ useReferralCode()                                // 第一层 ✓
├─ const auth = useAuth({ setMessage, showError, text, navigate, refreshAll, refreshSetupStatus })
│     → { token, user, isAdmin, busy, login, register, logout, resetAndLogin, localTestLogin, bootstrapAdmin, ... }
├─ const route = useHashRoute(auth.user, language)  // 第一层 ✓（接受 user）
├─ const billing = useBilling({ token, setMessage, showError, text })
│     → { balance, transactions, packages, customRechargeOptions, orders, checkout, adminPackages, pricing, imageModels, loadBilling, createPaymentOrder, startCheckout, ... }
├─ const jobs = useJobsGallery({ token, setMessage, showError, text, confirm, navigate, galleryRetentionLimit })
│     → { jobs, galleryQuota, selectedJobId, retryingJobId, loadJobs, createJob, createJobs, createRawImageJob, retryJob, deleteJob, saveSequenceAlignment, pixelizeCandidate, expandGalleryQuota, ... }
├─ const packs = usePacks({ token, setMessage, showError, text, confirm, navigate })
│     → { packs, packQuota, selectedPack, selectedPackJobs, loadPacks, createPack, selectPack, renamePack, toggleArchivePack, deletePack, downloadPack, addJobToPack, removeJobFromPack, expandPackLimit, ... }
├─ const admin = useAdmin({ token, isAdmin, setMessage, showError, text })
│     → { adminUsers, adminJobs, systemSettings, adminDashboard, loadAdmin, adjustCredits, adjustCreditsBatch, updatePricing, updateSetting, announcements, adminRetryJob, ... }
└─ refreshAll = useCallback(() => Promise.all([billing.load, jobs.load, packs.load, admin.load]), [...])
```

## 4. 难点与解法

### 4.1 refreshCore 全量刷新协调（核心难点）
现状：写操作后 `await refreshCore(token)` 一次性拉所有域（粗糙但安全）。
**方案 A（推荐）**：每个域 hook 暴露 `load(token)`；App 组合 `refreshAll = () => Promise.all([billing.load, jobs.load, packs.load, admin.load])`。把 `refreshAll` 作为依赖注入回各域 hook 的操作（因为 `createJob` 影响 balance+jobs+quota，需刷新多域）。
**注意循环**：域 hook 的操作需要 `refreshAll`，而 `refreshAll` 由各域 `load` 组成 → 用 `useRef` 持有 `refreshAll` 最新引用，或把 `refreshAll` 经参数在 App 层注入操作（操作定义在 hook 内但接受 `refreshAll` 参数）。

### 4.2 跨域共享数据（pricing / imageModels）
`pricing` 用于 workspace/gallery/admin；`imageModels` 用于 workspace/raw。**不属于单一域**。
**方案**：放入 `useBilling`（或新建 `useReferenceData`）统一拥有，按 props 透传给需要的页面。

### 4.3 user ↔ page ↔ navigate 循环
`useHashRoute(user)` 需要 `user`（admin 页守卫），而操作需要 `navigate`。
**解法**：`useAuth` 先于 `useHashRoute` 调用（auth 拥有 user）；`navigate` 来自 `useHashRoute`（在 auth 后）；auth 的操作若需 `navigate`（如 bootstrapAdmin → admin），用 `useRef` 持有 navigate 或在 App 层把 navigate 注入 auth 操作。第一层 `useHashRoute` 已可接受 `user`，结构已就位。

### 4.4 token 所有权
`token` + `setToken` 由 `useAuth` 拥有，其他域 hook 通过 `deps.token` 接受（只读）。登出时 auth 清 token，各域 hook 监听 token 变为空 → 清空自身 state（`useEffect([token])`）。

## 5. 分步执行计划（每步 `tsc` + 浏览器渲染 + 关键交互验证）

1. **补测试**（见 §2）
2. **useBilling**（最独立，无 confirm/navigate 依赖）→ 验证账单页
3. **useAdmin**（独立，admin only）→ 验证管理页
4. **usePacks** → 验证素材包页
5. **useJobsGallery**（最核心，依赖 confirm/navigate/retention）→ 验证生成 + 画廊
6. **useAuth** + `refreshAll` 协调 + `poll` 归位 → 验证登录/登出/轮询
7. **App.tsx 组装**：删除已迁移的 state/操作，只留 hooks 调用 + render（目标 ≤ 250 行）
8. **全回归**（见 §6）

> 每步保持 App.tsx 可编译可运行；先并存（hook 提供 + App 旧逻辑删除）逐域切换，避免一次性大爆破。

## 6. 回归验证清单（登录态逐条手验，直到有自动化测试）

- [ ] 登录 / 登出 / 注册 / 重置密码 / 本地测试账号 / bootstrap admin
- [ ] 生成：单张 / 批量 / 原图；作品库自动刷新；超额清理确认弹窗
- [ ] 画廊：选择 / 重试 / 删除 / 序列帧对齐保存
- [ ] 素材包：创建 / 打开 / 重命名 / 归档 / 删除 / 下载 / 加入-移出作品 / 扩容
- [ ] 充值：套餐下单 / 自定义 / checkout / mock 支付 / 订单刷新 / 支付返回 hash
- [ ] 管理：调点 / 批量调点 / 退款 / 价格 / 配置 / 公告 / 重试-取消任务
- [ ] 轮询：稳定期不重渲染；任务状态变化时更新
- [ ] 暗色 / 亮色；移动端

## 7. 完成标准
- App.tsx ≤ 250 行（组装 + render）
- 每个业务域是独立、可单测的 hook
- 全部回归清单通过
- 版本号 B 位递增（架构能力提升）
