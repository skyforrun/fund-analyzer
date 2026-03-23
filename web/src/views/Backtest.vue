<script setup lang="ts">
import { ref, computed } from 'vue'
import { useBacktestStore } from '@/stores/backtest'
import { formatMoney, formatPercent } from '@/composables/useDecimal'
import MetricCard from '@/components/common/MetricCard.vue'
import LineChart from '@/components/charts/LineChart.vue'
import AreaChart from '@/components/charts/AreaChart.vue'
import HeatmapChart from '@/components/charts/HeatmapChart.vue'

const store = useBacktestStore()

// 回测参数
const startDate = ref('2020-01-01')
const endDate = ref('')
const initialCapital = ref(100000)
const coreRatio = ref(30)
const benchmarkCode = ref('000300')

const benchmarkOptions = [
  { value: '000688', label: '科创50' },
  { value: '000300', label: '沪深300' },
]

// 运行回测
function handleRun() {
  store.runBacktest({
    start_date: startDate.value,
    end_date: endDate.value || undefined,
    initial_capital: initialCapital.value,
    core_ratio: coreRatio.value / 100,
    benchmark_code: benchmarkCode.value,
  })
}

// 净值曲线数据
const navSeries = computed(() => {
  const r = store.result
  if (!r) return []

  // 组合净值曲线
  const series = [
    {
      name: '组合净值',
      dates: r.portfolio_values.dates,
      values: r.portfolio_values.values,
    },
  ]

  // 基准净值曲线: (1+r1)*(1+r2)*...* initial_capital
  if (r.benchmark_returns.dates.length) {
    const benchValues: number[] = []
    let cum = r.initial_capital
    for (let i = 0; i < r.benchmark_returns.values.length; i++) {
      cum *= 1 + r.benchmark_returns.values[i]
      benchValues.push(Number(cum.toFixed(2)))
    }
    series.push({
      name: '基准净值',
      dates: r.benchmark_returns.dates,
      values: benchValues,
    })
  }

  return series
})

// 回撤曲线数据
const drawdownData = computed(() => {
  const r = store.result
  if (!r) return { dates: [] as string[], values: [] as number[] }

  const values = r.portfolio_values.values
  const drawdowns: number[] = []
  let peak = values[0] ?? 0
  for (const v of values) {
    if (v > peak) peak = v
    const dd = peak > 0 ? ((v - peak) / peak) * 100 : 0
    drawdowns.push(Number(dd.toFixed(2)))
  }

  return {
    dates: r.portfolio_values.dates,
    values: drawdowns,
  }
})

// 绩效指标
const metricCards = computed(() => {
  const m = store.result?.metrics
  if (!m) return []
  return [
    { title: '年化收益率', value: formatPercent(m.annualized_return * 100), suffix: '%', trend: m.annualized_return >= 0 ? 'up' as const : 'down' as const },
    { title: '年化波动率', value: formatPercent(m.annualized_volatility * 100), suffix: '%', trend: undefined },
    { title: '最大回撤', value: formatPercent(m.max_drawdown * 100), suffix: '%', trend: 'down' as const },
    { title: '夏普比率', value: m.sharpe_ratio.toFixed(2), suffix: undefined, trend: m.sharpe_ratio >= 0 ? 'up' as const : 'down' as const },
    { title: '索提诺比率', value: m.sortino_ratio.toFixed(2), suffix: undefined, trend: m.sortino_ratio >= 0 ? 'up' as const : 'down' as const },
    { title: '卡尔玛比率', value: m.calmar_ratio.toFixed(2), suffix: undefined, trend: m.calmar_ratio >= 0 ? 'up' as const : 'down' as const },
    { title: '月度胜率', value: formatPercent(m.monthly_win_rate * 100), suffix: '%', trend: m.monthly_win_rate >= 0.5 ? 'up' as const : 'down' as const },
    { title: '信息比率', value: m.information_ratio !== null ? m.information_ratio.toFixed(2) : '-', suffix: undefined, trend: undefined },
    { title: 'Alpha', value: m.alpha !== null ? formatPercent(m.alpha * 100) : '-', suffix: m.alpha !== null ? '%' : undefined, trend: m.alpha !== null ? (m.alpha >= 0 ? 'up' as const : 'down' as const) : undefined },
  ]
})

// 摘要数据
const summaryCards = computed(() => {
  const r = store.result
  if (!r) return []
  const totalReturn = r.initial_capital > 0 ? (r.final_value - r.initial_capital) / r.initial_capital : 0
  return [
    { title: '初始资金', value: formatMoney(r.initial_capital), trend: undefined },
    { title: '最终市值', value: formatMoney(r.final_value), trend: r.final_value >= r.initial_capital ? 'up' as const : 'down' as const },
    { title: '总收益率', value: formatPercent(totalReturn * 100), suffix: '%', trend: totalReturn >= 0 ? 'up' as const : 'down' as const },
    { title: '总费用', value: formatMoney(r.total_fees_paid), trend: undefined },
  ]
})

// 月度收益热力图数据
const heatmapDates = computed(() => store.result?.portfolio_returns.dates ?? [])
const heatmapValues = computed(() => store.result?.portfolio_returns.values ?? [])
</script>

<template>
  <div class="backtest">
    <!-- 参数面板 -->
    <el-card shadow="hover" class="param-card">
      <el-form label-width="90px">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :lg="6">
            <el-form-item label="开始日期">
              <el-date-picker
                v-model="startDate"
                type="date"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                placeholder="选择开始日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6">
            <el-form-item label="结束日期">
              <el-date-picker
                v-model="endDate"
                type="date"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                placeholder="默认至今"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6">
            <el-form-item label="初始资金">
              <el-input-number
                v-model="initialCapital"
                :min="10000"
                :step="10000"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6">
            <el-form-item label="基准指数">
              <el-select v-model="benchmarkCode" style="width: 100%">
                <el-option
                  v-for="opt in benchmarkOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :xs="24" :sm="16" :lg="12">
            <el-form-item label="核心仓占比">
              <div class="ratio-slider">
                <el-slider v-model="coreRatio" :min="0" :max="100" :step="5" show-input style="flex: 1" />
                <span class="ratio-hint">卫星仓: {{ 100 - coreRatio }}%</span>
              </div>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="8" :lg="4">
            <el-form-item>
              <el-button type="primary" :loading="store.loading" @click="handleRun" style="width: 100%">
                运行回测
              </el-button>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 回测结果 -->
    <template v-if="store.result">
      <!-- 摘要指标 -->
      <el-row :gutter="16" class="metric-row">
        <el-col :xs="24" :sm="12" :lg="6" v-for="(m, i) in summaryCards" :key="'s' + i">
          <MetricCard :title="m.title" :value="m.value" :suffix="m.suffix" :trend="m.trend" />
        </el-col>
      </el-row>

      <!-- 净值曲线 -->
      <el-card shadow="hover" class="chart-card">
        <template #header>
          <span class="card-title">净值曲线</span>
        </template>
        <LineChart :series="navSeries" y-axis-format="value" />
      </el-card>

      <!-- 回撤曲线 -->
      <el-card shadow="hover" class="chart-card">
        <template #header>
          <span class="card-title">回撤曲线</span>
        </template>
        <AreaChart
          :dates="drawdownData.dates"
          :values="drawdownData.values"
          color="#F56C6C"
        />
      </el-card>

      <!-- 绩效指标 -->
      <el-card shadow="hover" class="chart-card">
        <template #header>
          <span class="card-title">绩效指标</span>
        </template>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12" :lg="8" v-for="(m, i) in metricCards" :key="'m' + i" class="metric-col">
            <MetricCard :title="m.title" :value="m.value" :suffix="m.suffix" :trend="m.trend" />
          </el-col>
        </el-row>
      </el-card>

      <!-- 月度收益热力图 -->
      <el-card shadow="hover" class="chart-card">
        <template #header>
          <span class="card-title">月度收益热力图</span>
        </template>
        <HeatmapChart :dates="heatmapDates" :values="heatmapValues" />
      </el-card>
    </template>

    <!-- 空状态 -->
    <el-card v-else-if="!store.loading" shadow="hover" class="chart-card">
      <el-empty description="请设置参数并运行回测" />
    </el-card>

    <!-- 加载中 -->
    <el-card v-if="store.loading && !store.result" shadow="hover" class="chart-card" v-loading="true" style="min-height: 300px" />
  </div>
</template>

<style scoped lang="scss">
.backtest {
  max-width: 1400px;
}

.param-card {
  margin-bottom: 16px;

  :deep(.el-card__body) {
    padding-bottom: 2px;
  }
}

.metric-row {
  margin-bottom: 16px;
}

.metric-col {
  margin-bottom: 12px;
}

.chart-card {
  margin-bottom: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.ratio-slider {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.ratio-hint {
  white-space: nowrap;
  font-size: 13px;
  color: #909399;
}
</style>
