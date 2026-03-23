import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  getConfig,
  getNotificationConfig,
  updateNotificationConfig,
  getNotificationRules,
  updateNotificationRules,
  sendTestNotification,
} from '@/api/settings'
import type { NotificationConfig, NotificationRule } from '@/types/settings'

export const useSettingsStore = defineStore('settings', () => {
  const config = ref<Record<string, any> | null>(null)
  const notificationConfig = ref<NotificationConfig | null>(null)
  const notificationRules = ref<NotificationRule[]>([])
  const configLoading = ref(false)
  const notifLoading = ref(false)
  const rulesLoading = ref(false)

  async function fetchConfig() {
    configLoading.value = true
    try {
      const res = await getConfig()
      config.value = res.data
    } catch {
      // 错误已在拦截器中处理
    } finally {
      configLoading.value = false
    }
  }

  async function fetchNotificationConfig() {
    notifLoading.value = true
    try {
      const res = await getNotificationConfig()
      notificationConfig.value = res.data
    } catch {
      // 错误已在拦截器中处理
    } finally {
      notifLoading.value = false
    }
  }

  async function saveNotificationConfig(data: { webhook_url: string; enabled: boolean }) {
    const res = await updateNotificationConfig(data)
    notificationConfig.value = res.data
  }

  async function fetchNotificationRules() {
    rulesLoading.value = true
    try {
      const res = await getNotificationRules()
      notificationRules.value = res.data ?? []
    } catch {
      // 错误已在拦截器中处理
    } finally {
      rulesLoading.value = false
    }
  }

  async function saveNotificationRules(rules: NotificationRule[]) {
    await updateNotificationRules(rules)
  }

  async function testNotification() {
    const res = await sendTestNotification()
    return res.data?.success ?? false
  }

  return {
    config,
    notificationConfig,
    notificationRules,
    configLoading,
    notifLoading,
    rulesLoading,
    fetchConfig,
    fetchNotificationConfig,
    saveNotificationConfig,
    fetchNotificationRules,
    saveNotificationRules,
    testNotification,
  }
})
