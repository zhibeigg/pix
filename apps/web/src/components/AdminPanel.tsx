import { AdminConsole, type AdminConsoleProps } from '../features/admin/AdminConsole'

/** 兼容旧导入路径；后台实现已迁移到 features/admin。 */
export function AdminPanel(props: AdminConsoleProps) {
  return <AdminConsole {...props} />
}

export type { AdminConsoleProps as AdminPanelProps }
