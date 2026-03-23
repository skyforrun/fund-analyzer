<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart as BarChartType } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChartType, TitleComponent, TooltipComponent, GridComponent, CanvasRenderer])

const props = withDefaults(
  defineProps<{
    categories: string[]
    values: number[]
    title?: string
    color?: string
  }>(),
  {
    title: '',
    color: '#409EFF',
  },
)

const option = computed(() => ({
  title: props.title
    ? {
        text: props.title,
        left: 'center',
        textStyle: { fontSize: 14, fontWeight: 600 },
      }
    : undefined,
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: 20,
    top: props.title ? 40 : 20,
    containLabel: true,
  },
  xAxis: {
    type: 'category',
    data: props.categories,
    axisLabel: { fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    axisLabel: { fontSize: 11 },
  },
  series: [
    {
      type: 'bar',
      data: props.values,
      itemStyle: {
        color: props.color,
        borderRadius: [4, 4, 0, 0],
      },
      barMaxWidth: 40,
    },
  ],
}))
</script>

<template>
  <v-chart :option="option" autoresize style="height: 300px; width: 100%" />
</template>
