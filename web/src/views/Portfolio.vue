<script setup lang="ts">
import { onMounted, reactive, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { usePortfolioStore } from '@/stores/portfolio'
import { formatMoney, formatPercent } from '@/composables/useDecimal'
import MetricCard from '@/components/common/MetricCard.vue'
import type { BuyRequest, SellRequest } from '@/types/portfolio'
import type { FormInstance } from 'element-plus'

const store = usePortfolioStore()

// 指标卡
const metrics = computed(() => {
  const s = store.summary
  if (!s) return []
  return [
    {
      title: '总市值',
      value: formatMoney(s.total_market_value),
      trend: undefined,
    },
    {
      title: '总收益',
      value: formatMoney(s.total_pnl),
      trend: s.total_pnl >= 0 ? ('up' as const) : ('down' as const),
    },
    {
      title: '收益率',
      value: formatPercent(s.total_return_pct),
      suffix: '%',
      trend: s.total_return_pct >= 0 ? ('up' as const) : ('down' as const),
    },
  ]
})

// 买入表单
const buyFormRef = ref<FormInstance>()
const buyForm = reactive<BuyRequest>({
  fund_code: '',
  amount: 0,
  nav: 0,
  position_type: '核心',
})
const buyLoading = ref(false)

const buyRules = {
  fund_code: [{ required: true, message: '请输入基金代码', trigger: 'blur' }],
  amount: [{ required: true, message: '请输入金额', trigger: 'blur' }],
  nav: [{ required: true, message: '请输入净值', trigger: 'blur' }],
  position_type: [{ required: true, message: '请选择仓位类型', trigger: 'change' }],
}

async function handleBuy() {
  const valid = await buyFormRef.value?.validate().catch(() => false)
  if (!valid) return
  buyLoading.value = true
  try {
    await store.executeBuy({ ...buyForm })
    ElMessage.success('买入成功')
    buyFormRef.value?.resetFields()
    refreshData()
  } catch {
    // 错误已在拦截器中处理
  } finally {
    buyLoading.value = false
  }
}

// 卖出表单
const sellFormRef = ref<FormInstance>()
const sellForm = reactive<SellRequest>({
  fund_code: '',
  shares: 0,
  nav: 0,
})
const sellLoading = ref(false)

const sellRules = {
  fund_code: [{ required: true, message: '请输入基金代码', trigger: 'blur' }],
  shares: [{ required: true, message: '请输入份额', trigger: 'blur' }],
  nav: [{ required: true, message: '请输入净值', trigger: 'blur' }],
}

async function handleSell() {
  const valid = await sellFormRef.value?.validate().catch(() => false)
  if (!valid) return
  sellLoading.value = true
  try {
    await store.executeSell({ ...sellForm })
    ElMessage.success('卖出成功')
    sellFormRef.value?.resetFields()
    refreshData()
  } catch {
    // 错误已在拦截器中处理
  } finally {
    sellLoading.value = false
  }
}

// 收益率着色
function pnlClass(val: number) {
  return val >= 0 ? 'text-up' : 'text-down'
}

// 刷新数据
function refreshData() {
  store.fetchSummary()
  store.fetchHoldings()
}

onMounted(() => {
  store.fetchSummary()
  store.fetchHoldings()
})
</script>

<template>
  <div class="portfolio-page">
    <!-- 持仓概览 -->
    <el-row :gutter="16" class="metric-row" v-loading="store.summaryLoading">
      <el-col :xs="24" :sm="8" v-for="(m, i) in metrics" :key="i">
        <MetricCard :title="m.title" :value="m.value" :suffix="m.suffix" :trend="m.trend" />
      </el-col>
    </el-row>

    <!-- 持仓明细 -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <span class="card-title">持仓明细</span>
      </template>
      <el-table
        :data="store.holdings"
        stripe
        v-loading="store.holdingsLoading"
        empty-text="暂无持仓数据"
        style="width: 100%"
      >
        <el-table-column prop="fund_code" label="基金代码" width="120" />
        <el-table-column prop="fund_name" label="基金名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="position_type" label="仓位类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag
              v-if="row.position_type"
              :type="row.position_type === '核心' ? 'primary' : 'warning'"
              size="small"
            >
              {{ row.position_type }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="shares" label="份额" width="120" align="right">
          <template #default="{ row }">{{ row.shares.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="cost_price" label="成本价" width="110" align="right">
          <template #default="{ row }">{{ row.cost_price.toFixed(4) }}</template>
        </el-table-column>
        <el-table-column prop="buy_date" label="买入日期" width="120" align="center">
          <template #default="{ row }">{{ row.buy_date ?? '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 买入/卖出 -->
    <el-row :gutter="16" class="section-card">
      <el-col :xs="24" :md="12">
        <el-card shadow="hover">
          <template #header>
            <span class="card-title">买入</span>
          </template>
          <el-form
            ref="buyFormRef"
            :model="buyForm"
            :rules="buyRules"
            label-width="80px"
            label-position="left"
          >
            <el-form-item label="基金代码" prop="fund_code">
              <el-input v-model="buyForm.fund_code" placeholder="如 000001" />
            </el-form-item>
            <el-form-item label="买入金额" prop="amount">
              <el-input-number v-model="buyForm.amount" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
            <el-form-item label="当前净值" prop="nav">
              <el-input-number v-model="buyForm.nav" :min="0" :precision="4" style="width: 100%" />
            </el-form-item>
            <el-form-item label="仓位类型" prop="position_type">
              <el-select v-model="buyForm.position_type" style="width: 100%">
                <el-option label="核心仓" value="核心" />
                <el-option label="卫星仓" value="卫星" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="buyLoading" @click="handleBuy">确认买入</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="12">
        <el-card shadow="hover">
          <template #header>
            <span class="card-title">卖出</span>
          </template>
          <el-form
            ref="sellFormRef"
            :model="sellForm"
            :rules="sellRules"
            label-width="80px"
            label-position="left"
          >
            <el-form-item label="基金代码" prop="fund_code">
              <el-select
                v-model="sellForm.fund_code"
                filterable
                allow-create
                placeholder="选择或输入基金代码"
                style="width: 100%"
              >
                <el-option
                  v-for="h in store.holdings"
                  :key="h.fund_code"
                  :label="`${h.fund_code} - ${h.fund_name ?? ''}`"
                  :value="h.fund_code"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="卖出份额" prop="shares">
              <el-input-number v-model="sellForm.shares" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
            <el-form-item label="当前净值" prop="nav">
              <el-input-number v-model="sellForm.nav" :min="0" :precision="4" style="width: 100%" />
            </el-form-item>
            <el-form-item>
              <el-button type="danger" :loading="sellLoading" @click="handleSell">确认卖出</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <!-- 分红记录（可折叠） -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">分红记录</span>
          <el-button text type="primary" @click="store.fetchDividends()">
            <el-icon><Refresh /></el-icon> 加载数据
          </el-button>
        </div>
      </template>
      <el-table
        :data="store.dividends"
        stripe
        v-loading="store.dividendsLoading"
        empty-text="暂无分红记录，点击加载数据按钮获取"
        style="width: 100%"
      >
        <el-table-column prop="fund_code" label="基金代码" width="120" />
        <el-table-column prop="ex_date" label="除息日" width="120" />
        <el-table-column prop="dividend_per_unit" label="每份分红" width="120" align="right">
          <template #default="{ row }">
            {{ row.dividend_per_unit != null ? row.dividend_per_unit.toFixed(4) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="dividend_type" label="分红方式" width="120">
          <template #default="{ row }">{{ row.dividend_type ?? '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 赎回费率（可折叠） -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">赎回费率</span>
          <el-button text type="primary" @click="store.fetchFeeRates()">
            <el-icon><Refresh /></el-icon> 加载数据
          </el-button>
        </div>
      </template>
      <el-table
        :data="store.feeRates"
        stripe
        v-loading="store.feeRatesLoading"
        empty-text="暂无费率数据，点击加载数据按钮获取"
        style="width: 100%"
      >
        <el-table-column prop="fund_code" label="基金代码" width="120" />
        <el-table-column prop="holding_days" label="持有天数" width="120" align="right" />
        <el-table-column prop="fee_rate" label="费率" width="120" align="right">
          <template #default="{ row }">
            {{ row.fee_rate != null ? (row.fee_rate * 100).toFixed(2) + '%' : '-' }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.portfolio-page {
  max-width: 1400px;
}

.metric-row {
  margin-bottom: 16px;
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
