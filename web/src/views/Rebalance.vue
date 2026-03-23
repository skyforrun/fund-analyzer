<script setup lang="ts">
import { ref } from 'vue'
import { generateRebalance } from '@/api/rebalance'
import type { RebalanceResult } from '@/types/rebalance'

const loading = ref(false)
const result = ref<RebalanceResult | null>(null)

async function handleGenerate() {
  loading.value = true
  try {
    const res = await generateRebalance()
    result.value = res.data
  } catch {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false
  }
}

function actionType(action: string) {
  if (action.includes('买入')) return 'success'
  if (action.includes('卖出')) return 'danger'
  return 'info'
}

function positionLabel(type: string) {
  const map: Record<string, string> = {
    core: '核心仓',
    satellite: '卫星仓',
    '核心': '核心仓',
    '卫星': '卫星仓',
  }
  return map[type] ?? type
}
</script>

<template>
  <div class="rebalance-page">
    <!-- 操作按钮 -->
    <el-card shadow="hover" class="section-card">
      <div class="action-bar">
        <el-button type="primary" :loading="loading" @click="handleGenerate">
          生成调仓建议
        </el-button>
        <span v-if="result" class="as-of-text">数据截至: {{ result.as_of }}</span>
      </div>
    </el-card>

    <template v-if="result">
      <!-- 调仓行动列表 -->
      <el-card shadow="hover" class="section-card">
        <template #header>
          <span class="card-title">调仓行动</span>
        </template>
        <el-table
          :data="result.actions"
          stripe
          empty-text="暂无调仓建议"
          style="width: 100%"
        >
          <el-table-column prop="fund_code" label="基金代码" width="120" />
          <el-table-column prop="position_type" label="仓位类型" width="120" align="center">
            <template #default="{ row }">
              <el-tag
                :type="row.position_type === 'core' || row.position_type === '核心' ? 'primary' : 'warning'"
                size="small"
              >
                {{ positionLabel(row.position_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="action" label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="actionType(row.action)" size="small">
                {{ row.action }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="原因" min-width="250" show-overflow-tooltip />
        </el-table>
      </el-card>

      <!-- 推荐列表 -->
      <el-row :gutter="16">
        <el-col :xs="24" :md="12">
          <el-card shadow="hover" class="section-card">
            <template #header>
              <span class="card-title">核心仓推荐</span>
            </template>
            <el-table
              :data="result.core_picks"
              stripe
              empty-text="暂无推荐"
              style="width: 100%"
            >
              <el-table-column label="基金代码" width="120">
                <template #default="{ row }">{{ row[0] }}</template>
              </el-table-column>
              <el-table-column label="评分" align="right">
                <template #default="{ row }">{{ row[1].toFixed(2) }}</template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
        <el-col :xs="24" :md="12">
          <el-card shadow="hover" class="section-card">
            <template #header>
              <span class="card-title">卫星仓推荐</span>
            </template>
            <el-table
              :data="result.satellite_picks"
              stripe
              empty-text="暂无推荐"
              style="width: 100%"
            >
              <el-table-column label="基金代码" width="120">
                <template #default="{ row }">{{ row[0] }}</template>
              </el-table-column>
              <el-table-column label="评分" align="right">
                <template #default="{ row }">{{ row[1].toFixed(2) }}</template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </template>

    <!-- 空状态 -->
    <el-card v-else-if="!loading" shadow="hover" class="section-card">
      <el-empty description="点击上方按钮生成调仓建议" />
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.rebalance-page {
  max-width: 1400px;
}

.section-card {
  margin-bottom: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.action-bar {
  display: flex;
  align-items: center;
  gap: 16px;
}

.as-of-text {
  font-size: 13px;
  color: #909399;
}
</style>
