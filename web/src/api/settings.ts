import request from './request'
import type { ApiResponse } from '@/types'
import type { NotificationConfig, NotificationRule } from '@/types/settings'

/** 获取系统配置 */
export function getConfig() {
  return request.get<any, ApiResponse<Record<string, any>>>('/settings/config')
}

/** 获取通知配置 */
export function getNotificationConfig() {
  return request.get<any, ApiResponse<NotificationConfig | null>>('/settings/notification')
}

/** 更新通知配置 */
export function updateNotificationConfig(data: { webhook_url: string; enabled: boolean }) {
  return request.put<any, ApiResponse<NotificationConfig>>('/settings/notification', data)
}

/** 获取通知规则 */
export function getNotificationRules() {
  return request.get<any, ApiResponse<NotificationRule[]>>('/settings/notification/rules')
}

/** 更新通知规则 */
export function updateNotificationRules(rules: NotificationRule[]) {
  return request.put<any, ApiResponse<null>>('/settings/notification/rules', rules)
}

/** 发送测试通知 */
export function sendTestNotification() {
  return request.post<any, ApiResponse<{ success: boolean }>>('/settings/notification/test')
}
