/** 通知配置 */
export interface NotificationConfig {
  id: number | null
  channel: string
  webhook_url: string | null
  enabled: boolean
  updated_at: string | null
}

/** 通知规则 */
export interface NotificationRule {
  id: number | null
  rule_type: string
  params: Record<string, any> | null
  enabled: boolean
}

/** 同步进度 */
export interface SyncProgress {
  current: number
  total: number
  message: string
}
