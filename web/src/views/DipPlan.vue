<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useDipStore } from '@/stores/dip'
import { formatMoney } from '@/composables/useDecimal'
import type { DipPlanCreate } from '@/types/dip'
import type { FormInstance } from 'element-plus'

const store = useDipStore()

// 新建对话框
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const createLoading = ref(false)
const form = reactive<DipPlanCreate>({
  fund_code: '',
  amount: 500,
  frequency: 'monthly',
  smart: false,
})

const formRules = {
  fund_code: [{ required: true, message: '请输入基金代码', trigger: 'blur' }],
  amount: [{ required: true, message: '请输入定投金额', trigger: 'blur' }],
  frequency: [{ required: true, message: '请选择定投频率', trigger: 'change' }],
}

const frequencyOptions = [
  { value: 'weekly', label: '每周' },
  { value: 'biweekly', label: '每两周' },
  { value: 'monthly', label: '每月' },
]

function frequencyLabel(val: string) {
  return frequencyOptions.find((o) => o.value === val)?.label ?? val
}

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

function statusType(status: string): TagType {
  const map: Record<string, TagType> = {
    active: 'success',
    paused: 'warning',
    stopped: 'danger',
  }
  return map[status] ?? 'info'
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    active: '运行中',
    paused: '已暂停',
    stopped: '已停止',
  }
  return map[status] ?? status
}

function openDialog() {
  dialogVisible.value = true
}

async function handleCreate() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  createLoading.value = true
  try {
    await store.addPlan({ ...form })
    ElMessage.success('定投计划创建成功')
    dialogVisible.value = false
    formRef.value?.resetFields()
    store.fetchPlans()
  } catch {
    // 错误已在拦截器中处理
  } finally {
    createLoading.value = false
  }
}

async function handlePause(id: number) {
  try {
    await store.pause(id)
    ElMessage.success('已暂停')
    store.fetchPlans()
  } catch {
    // 错误已在拦截器中处理
  }
}

async function handleResume(id: number) {
  try {
    await store.resume(id)
    ElMessage.success('已恢复')
    store.fetchPlans()
  } catch {
    // 错误已在拦截器中处理
  }
}

async function handleStop(id: number) {
  try {
    await ElMessageBox.confirm('确定要停止该定投计划吗？停止后无法恢复。', '确认停止', {
      type: 'warning',
    })
    await store.stop(id)
    ElMessage.success('已停止')
    store.fetchPlans()
  } catch {
    // 取消或错误
  }
}

onMounted(() => {
  store.fetchPlans()
  store.fetchDue()
})
</script>

<template>
  <div class="dip-page">
    <!-- 到期提醒 -->
    <el-alert
      v-if="store.dueItems.length > 0"
      type="warning"
      :closable="false"
      class="due-alert"
    >
      <template #title>
        <span>今日有 {{ store.dueItems.length }} 笔定投到期</span>
      </template>
      <div v-for="item in store.dueItems" :key="item.plan_id" class="due-item">
        基金 {{ item.fund_code }}，金额 {{ formatMoney(item.amount) }}
        <el-tag v-if="item.smart_dip" size="small" type="success" style="margin-left: 8px">智能</el-tag>
      </div>
    </el-alert>

    <!-- 计划列表 -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">定投计划</span>
          <el-button type="primary" @click="openDialog">
            <el-icon><Plus /></el-icon> 新建计划
          </el-button>
        </div>
      </template>
      <el-table
        :data="store.plans"
        stripe
        v-loading="store.plansLoading"
        empty-text="暂无定投计划"
        style="width: 100%"
      >
        <el-table-column prop="fund_code" label="基金代码" width="120" />
        <el-table-column prop="amount" label="定投金额" width="120" align="right">
          <template #default="{ row }">{{ formatMoney(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="frequency" label="频率" width="100" align="center">
          <template #default="{ row }">{{ frequencyLabel(row.frequency) }}</template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="120" align="center">
          <template #default="{ row }">{{ row.start_date ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="smart_dip" label="智能定投" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.smart_dip" type="success" size="small">是</el-tag>
            <span v-else>否</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'active'"
              type="warning"
              size="small"
              text
              @click="handlePause(row.id)"
            >暂停</el-button>
            <el-button
              v-if="row.status === 'paused'"
              type="success"
              size="small"
              text
              @click="handleResume(row.id)"
            >恢复</el-button>
            <el-button
              v-if="row.status !== 'stopped'"
              type="danger"
              size="small"
              text
              @click="handleStop(row.id)"
            >停止</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建计划对话框 -->
    <el-dialog v-model="dialogVisible" title="新建定投计划" width="500px" destroy-on-close>
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="90px"
        label-position="left"
      >
        <el-form-item label="基金代码" prop="fund_code">
          <el-input v-model="form.fund_code" placeholder="如 000001" />
        </el-form-item>
        <el-form-item label="定投金额" prop="amount">
          <el-input-number v-model="form.amount" :min="100" :step="100" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="定投频率" prop="frequency">
          <el-select v-model="form.frequency" style="width: 100%">
            <el-option
              v-for="opt in frequencyOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="智能定投">
          <el-switch v-model="form.smart" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="handleCreate">确认创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.dip-page {
  max-width: 1400px;
}

.due-alert {
  margin-bottom: 16px;
}

.due-item {
  margin-top: 4px;
  font-size: 13px;
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
</style>
