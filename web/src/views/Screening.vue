<script setup lang="ts">
import { ref, computed } from 'vue'
import { useScreeningStore } from '@/stores/screening'
import { formatPercent } from '@/composables/useDecimal'
import type { ScreenResultItem, FeeScheduleItem } from '@/types/screening'

const store = useScreeningStore()

// 筛选参数
const positionType = ref('core')
const topN = ref(10)

// 费率弹窗
const feeDialogVisible = ref(false)
const currentFundCode = ref('')
const currentFundName = ref('')

// 执行筛选
function handleScreen() {
  store.fetchScore(positionType.value, topN.value)
}

// 查看费率
async function handleViewFees(row: ScreenResultItem) {
  currentFundCode.value = row.fund_code
  currentFundName.value = row.fund_name ?? row.fund_code
  feeDialogVisible.value = true
  await store.fetchFees(row.fund_code)
}

// 分离申购/赎回费率
const purchaseFees = computed(() =>
  store.fees.filter((f) => f.fee_type === '申购'),
)
const redemptionFees = computed(() =>
  store.fees.filter((f) => f.fee_type === '赎回'),
)

// 评分进度条颜色
function scoreColor(score: number): string {
  if (score >= 80) return '#67C23A'
  if (score >= 60) return '#409EFF'
  if (score >= 40) return '#E6A23C'
  return '#F56C6C'
}

// 信号标签类型
type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'
function actionTagType(action: string | null): TagType {
  if (!action) return 'info'
  if (action.includes('买入')) return 'success'
  if (action.includes('卖出')) return 'danger'
  if (action.includes('持有')) return 'warning'
  return 'info'
}

// 费率展示
function formatFeeRate(rate: number): string {
  return rate >= 0.01 ? `${(rate * 100).toFixed(2)}%` : `${(rate * 100).toFixed(4)}%`
}

function formatAmount(val: number | null): string {
  if (val === null) return '不限'
  return `¥${val.toLocaleString('zh-CN')}`
}

function formatDays(min: number, max: number): string {
  if (max === 0 && min === 0) return '不限'
  if (max === 0) return `≥${min}天`
  if (min === 0) return `<${max}天`
  return `${min}-${max}天`
}
</script>

<template>
  <div class="screening">
    <!-- 参数面板 -->
    <el-card shadow="hover" class="param-card">
      <el-form :inline="true">
        <el-form-item label="仓位类型">
          <el-select v-model="positionType" style="width: 140px">
            <el-option label="核心仓" value="core" />
            <el-option label="卫星仓" value="satellite" />
          </el-select>
        </el-form-item>
        <el-form-item label="筛选数量">
          <el-input-number v-model="topN" :min="1" :max="50" :step="5" style="width: 140px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="store.loading" @click="handleScreen">
            开始筛选
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 筛选结果 -->
    <el-card shadow="hover" class="result-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">筛选结果</span>
          <el-tag v-if="store.results.length" type="info" size="small">
            共 {{ store.results.length }} 只基金
          </el-tag>
        </div>
      </template>
      <el-table
        :data="store.results"
        stripe
        v-loading="store.loading"
        empty-text="请先执行筛选"
        style="width: 100%"
        @row-click="handleViewFees"
        row-class-name="clickable-row"
      >
        <el-table-column prop="fund_code" label="基金代码" width="110" />
        <el-table-column prop="fund_name" label="基金名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="fund_type" label="板块" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.fund_type ?? '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="评分" width="180" align="center" sortable>
          <template #default="{ row }">
            <div class="score-cell">
              <el-progress
                :percentage="row.score"
                :color="scoreColor(row.score)"
                :stroke-width="14"
                :text-inside="true"
                :format="() => row.score.toFixed(1)"
                style="width: 120px"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="action" label="信号" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.action" :type="actionTagType(row.action)" size="small">
              {{ row.action }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="90" align="center">
          <template #default="{ row }">{{ row.confidence ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="推荐理由" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.reason ?? '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 费率弹窗 -->
    <el-dialog
      v-model="feeDialogVisible"
      :title="`费率详情 - ${currentFundName}（${currentFundCode}）`"
      width="680px"
      destroy-on-close
    >
      <div v-loading="store.feesLoading" style="min-height: 100px">
        <template v-if="!store.feesLoading && store.fees.length > 0">
          <h4 class="fee-section-title">申购费率</h4>
          <el-table :data="purchaseFees" stripe size="small" empty-text="无申购费率数据" style="width: 100%">
            <el-table-column label="金额范围" min-width="150">
              <template #default="{ row }">
                {{ formatAmount(row.min_amount) }} - {{ formatAmount(row.max_amount) }}
              </template>
            </el-table-column>
            <el-table-column label="费率" width="120" align="right">
              <template #default="{ row }">{{ formatFeeRate(row.fee_rate) }}</template>
            </el-table-column>
          </el-table>

          <h4 class="fee-section-title" style="margin-top: 20px">赎回费率</h4>
          <el-table :data="redemptionFees" stripe size="small" empty-text="无赎回费率数据" style="width: 100%">
            <el-table-column label="持有天数" min-width="150">
              <template #default="{ row }">
                {{ formatDays(row.min_holding_days, row.max_holding_days) }}
              </template>
            </el-table-column>
            <el-table-column label="费率" width="120" align="right">
              <template #default="{ row }">{{ formatFeeRate(row.fee_rate) }}</template>
            </el-table-column>
          </el-table>
        </template>
        <el-empty v-else-if="!store.feesLoading" description="暂无费率数据" />
      </div>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.screening {
  max-width: 1400px;
}

.param-card {
  margin-bottom: 16px;

  :deep(.el-card__body) {
    padding-bottom: 2px;
  }
}

.result-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.score-cell {
  display: flex;
  align-items: center;
  justify-content: center;
}

.fee-section-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #303133;
}

:deep(.clickable-row) {
  cursor: pointer;
}
</style>
