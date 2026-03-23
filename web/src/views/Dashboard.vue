<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { usePolling } from '@/composables/usePolling'
import { formatMoney, formatPercent } from '@/composables/useDecimal'
import MetricCard from '@/components/common/MetricCard.vue'
import PieChart from '@/components/charts/PieChart.vue'

const store = useDashboardStore()

// 计算指标卡数据
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
      title: '总成本',
      value: formatMoney(s.total_cost),
      trend: undefined,
    },
    {
      title: '总收益',
      value: formatMoney(s.total_pnl),
      trend: s.total_pnl >= 0 ? 'up' as const : 'down' as const,
    },
    {
      title: '收益率',
      value: formatPercent(s.total_return_pct),
      suffix: '%',
      trend: s.total_return_pct >= 0 ? 'up' as const : 'down' as const,
    },
  ]
})

// 饼图数据
const pieData = computed(() => {
  if (!store.summary?.type_summary) return []
  return store.summary.type_summary.map((t) => ({
    name: t.position_type,
    value: Number(t.market_value.toFixed(2)),
  }))
})

// 收益率着色
function pnlClass(val: number) {
  return val >= 0 ? 'text-up' : 'text-down'
}

// 挂载时加载数据
onMounted(() => {
  store.fetchSummary()
  store.fetchEstimates()
})

// 交易时段轮询估值
usePolling(() => store.fetchEstimates(), 30000)
</script>

<template>
  <div class="dashboard">
    <!-- 指标卡 -->
    <el-row :gutter="16" class="metric-row" v-loading="store.summaryLoading">
      <el-col :xs="24" :sm="12" :lg="6" v-for="(m, i) in metrics" :key="i">
        <MetricCard :title="m.title" :value="m.value" :suffix="m.suffix" :trend="m.trend" />
      </el-col>
    </el-row>

    <!-- 配置饼图 + 持仓列表 -->
    <el-row :gutter="16" class="content-row">
      <el-col :xs="24" :lg="8">
        <el-card shadow="hover">
          <PieChart title="仓位配置" :data="pieData" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="16">
        <el-card shadow="hover">
          <template #header>
            <span class="card-title">持仓明细</span>
          </template>
          <el-table
            :data="store.summary?.holdings ?? []"
            stripe
            v-loading="store.summaryLoading"
            empty-text="暂无持仓数据"
            style="width: 100%"
          >
            <el-table-column prop="fund_code" label="基金代码" width="100" />
            <el-table-column prop="fund_name" label="基金名称" min-width="150" show-overflow-tooltip />
            <el-table-column prop="position_type" label="仓位" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.position_type === '核心' ? 'primary' : 'warning'" size="small">
                  {{ row.position_type }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="shares" label="份额" width="100" align="right">
              <template #default="{ row }">{{ row.shares.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column prop="cost_price" label="成本价" width="100" align="right">
              <template #default="{ row }">{{ row.cost_price.toFixed(4) }}</template>
            </el-table-column>
            <el-table-column prop="current_nav" label="最新净值" width="100" align="right">
              <template #default="{ row }">{{ row.current_nav.toFixed(4) }}</template>
            </el-table-column>
            <el-table-column prop="market_value" label="市值" width="120" align="right">
              <template #default="{ row }">{{ formatMoney(row.market_value) }}</template>
            </el-table-column>
            <el-table-column prop="pnl" label="收益" width="120" align="right">
              <template #default="{ row }">
                <span :class="pnlClass(row.pnl)">{{ formatMoney(row.pnl) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="return_pct" label="收益率" width="100" align="right">
              <template #default="{ row }">
                <span :class="pnlClass(row.return_pct)">{{ formatPercent(row.return_pct) }}%</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 实时估值 -->
    <el-row class="content-row">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="card-title">实时估值</span>
              <el-tag type="info" size="small">交易时段每30秒刷新</el-tag>
            </div>
          </template>
          <el-table
            :data="store.estimates"
            stripe
            v-loading="store.estimatesLoading"
            empty-text="暂无估值数据"
            style="width: 100%"
          >
            <el-table-column prop="fund_code" label="基金代码" width="120" />
            <el-table-column prop="fund_name" label="基金名称" min-width="200" show-overflow-tooltip />
            <el-table-column prop="estimate_nav" label="估算净值" width="120" align="right">
              <template #default="{ row }">{{ row.estimate_nav.toFixed(4) }}</template>
            </el-table-column>
            <el-table-column prop="estimate_change_pct" label="估算涨跌幅" width="130" align="right">
              <template #default="{ row }">
                <span :class="pnlClass(row.estimate_change_pct)">
                  {{ formatPercent(row.estimate_change_pct) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="estimate_time" label="估算时间" width="180" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped lang="scss">
.dashboard {
  max-width: 1400px;
}

.metric-row {
  margin-bottom: 16px;
}

.content-row {
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
