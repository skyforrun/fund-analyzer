<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  title: string
  value: string | number
  suffix?: string
  trend?: 'up' | 'down'
}>()

const trendClass = computed(() => {
  if (!props.trend) return ''
  return props.trend === 'up' ? 'trend-up' : 'trend-down'
})
</script>

<template>
  <el-card shadow="hover" class="metric-card">
    <div class="metric-title">{{ title }}</div>
    <div class="metric-value" :class="trendClass">
      {{ value }}
      <span v-if="suffix" class="metric-suffix">{{ suffix }}</span>
    </div>
    <div v-if="trend" class="metric-trend">
      <el-icon v-if="trend === 'up'"><Top /></el-icon>
      <el-icon v-else><Bottom /></el-icon>
    </div>
  </el-card>
</template>

<style scoped lang="scss">
.metric-card {
  height: 120px;

  :deep(.el-card__body) {
    display: flex;
    flex-direction: column;
    justify-content: center;
    height: 100%;
    padding: 16px 20px;
  }
}

.metric-title {
  font-size: 14px;
  color: $text-secondary;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 28px;
  font-weight: 700;
  color: $text-primary;
  line-height: 1.2;
}

.metric-suffix {
  font-size: 16px;
  font-weight: 400;
  margin-left: 2px;
}

.trend-up {
  color: $color-up;
}

.trend-down {
  color: $color-down;
}

.metric-trend {
  margin-top: 4px;
  font-size: 14px;
}
</style>
