<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useSettingsStore } from '@/stores/settings'
import { useSSE } from '@/composables/useSSE'
import type { NotificationRule } from '@/types/settings'

const store = useSettingsStore()

// SSE 数据同步
const sse = useSSE('/api/settings/sync/stream')
const syncing = ref(false)

function handleSync() {
  syncing.value = true
  sse.start()
}

// 监听 SSE 完成
const checkDone = () => {
  if (sse.done.value) {
    syncing.value = false
    ElMessage.success('数据同步完成')
  }
}

// 简单轮询 done 状态（watch 在 composable 外不方便）
// 改用 watchEffect
import { watchEffect } from 'vue'
watchEffect(() => {
  if (sse.done.value && syncing.value) {
    syncing.value = false
    ElMessage.success('数据同步完成')
  }
})

// 通知配置表单
const notifForm = reactive({
  webhook_url: '',
  enabled: false,
})
const notifSaving = ref(false)
const testLoading = ref(false)

async function loadNotifConfig() {
  await store.fetchNotificationConfig()
  if (store.notificationConfig) {
    notifForm.webhook_url = store.notificationConfig.webhook_url ?? ''
    notifForm.enabled = store.notificationConfig.enabled
  }
}

async function handleSaveNotif() {
  notifSaving.value = true
  try {
    await store.saveNotificationConfig({
      webhook_url: notifForm.webhook_url,
      enabled: notifForm.enabled,
    })
    ElMessage.success('通知配置已保存')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    notifSaving.value = false
  }
}

async function handleTestNotif() {
  testLoading.value = true
  try {
    const success = await store.testNotification()
    if (success) {
      ElMessage.success('测试通知发送成功')
    } else {
      ElMessage.warning('测试通知发送失败')
    }
  } catch {
    // 错误已在拦截器中处理
  } finally {
    testLoading.value = false
  }
}

// 通知规则
const rules = ref<NotificationRule[]>([])
const rulesSaving = ref(false)

async function loadRules() {
  await store.fetchNotificationRules()
  rules.value = store.notificationRules.map((r) => ({ ...r }))
}

async function handleSaveRules() {
  rulesSaving.value = true
  try {
    await store.saveNotificationRules(rules.value)
    ElMessage.success('通知规则已保存')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    rulesSaving.value = false
  }
}

// 配置项展示
function formatConfigValue(val: any): string {
  if (val === null || val === undefined) return '-'
  if (typeof val === 'object') return JSON.stringify(val, null, 2)
  return String(val)
}

onMounted(() => {
  store.fetchConfig()
  loadNotifConfig()
  loadRules()
})
</script>

<template>
  <div class="settings-page">
    <!-- 当前配置 -->
    <el-card shadow="hover" class="section-card" v-loading="store.configLoading">
      <template #header>
        <span class="card-title">当前配置</span>
      </template>
      <el-descriptions v-if="store.config" :column="2" border>
        <el-descriptions-item
          v-for="(value, key) in store.config"
          :key="String(key)"
          :label="String(key)"
        >
          <pre v-if="typeof value === 'object'" class="config-pre">{{ formatConfigValue(value) }}</pre>
          <span v-else>{{ formatConfigValue(value) }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <el-empty v-else description="暂无配置数据" />
    </el-card>

    <!-- 数据同步 -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <span class="card-title">数据同步</span>
      </template>
      <div class="sync-section">
        <el-button type="primary" :loading="syncing" @click="handleSync" :disabled="syncing">
          开始同步
        </el-button>
        <div v-if="syncing || sse.done.value" class="sync-progress">
          <el-progress
            :percentage="sse.progress.value"
            :status="sse.done.value ? 'success' : undefined"
            :stroke-width="20"
            style="margin: 16px 0"
          />
          <div class="sync-message">{{ sse.message.value }}</div>
        </div>
      </div>
    </el-card>

    <!-- 通知配置 -->
    <el-card shadow="hover" class="section-card" v-loading="store.notifLoading">
      <template #header>
        <span class="card-title">通知配置</span>
      </template>
      <el-form label-width="110px" label-position="left">
        <el-form-item label="Webhook URL">
          <el-input v-model="notifForm.webhook_url" placeholder="请输入 Webhook 地址" />
        </el-form-item>
        <el-form-item label="启用通知">
          <el-switch v-model="notifForm.enabled" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="notifSaving" @click="handleSaveNotif">保存配置</el-button>
          <el-button :loading="testLoading" @click="handleTestNotif">发送测试</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 通知规则 -->
    <el-card shadow="hover" class="section-card" v-loading="store.rulesLoading">
      <template #header>
        <div class="card-header">
          <span class="card-title">通知规则</span>
          <el-button type="primary" :loading="rulesSaving" @click="handleSaveRules">保存全部规则</el-button>
        </div>
      </template>
      <el-table
        :data="rules"
        stripe
        empty-text="暂无通知规则"
        style="width: 100%"
      >
        <el-table-column prop="rule_type" label="规则类型" width="160" />
        <el-table-column prop="params" label="参数" min-width="250">
          <template #default="{ row }">
            <span v-if="row.params">{{ JSON.stringify(row.params) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="启用" width="100" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" />
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.settings-page {
  max-width: 1200px;
}

.section-card {
  margin-bottom: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.config-pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 13px;
}

.sync-section {
  .sync-progress {
    margin-top: 8px;
  }

  .sync-message {
    font-size: 13px;
    color: #606266;
  }
}
</style>
