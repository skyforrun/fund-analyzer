<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart as LineChartType } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChartType, TitleComponent, TooltipComponent, LegendComponent, GridComponent, DataZoomComponent, CanvasRenderer])

interface SeriesItem {
  name: string
  dates: string[]
  values: number[]
}

const props = withDefaults(
  defineProps<{
    series: SeriesItem[]
    title?: string
    yAxisFormat?: string
  }>(),
  {
    title: '',
    yAxisFormat: 'value',
  },
)

const colors = ['#409EFF', '#E6A23C', '#67C23A', '#F56C6C', '#909399']

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
    axisPointer: { type: 'cross' },
    formatter(params: any[]) {
      let html = `<div style="font-weight:600">${params[0].axisValueLabel}</div>`
      for (const p of params) {
        const val = props.yAxisFormat === 'percent'
          ? `${(p.value as number).toFixed(2)}%`
          : `¥${(p.value as number).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
        html += `<div>${p.marker} ${p.seriesName}: ${val}</div>`
      }
      return html
    },
  },
  legend: {
    bottom: 0,
    data: props.series.map((s) => s.name),
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: 40,
    top: props.title ? 40 : 20,
    containLabel: true,
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: props.series[0]?.dates ?? [],
    axisLabel: { fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    axisLabel: {
      fontSize: 11,
      formatter: props.yAxisFormat === 'percent' ? '{value}%' : '¥{value}',
    },
  },
  dataZoom: [
    { type: 'inside', start: 0, end: 100 },
    { type: 'slider', start: 0, end: 100, height: 20, bottom: 24 },
  ],
  color: colors,
  series: props.series.map((s, i) => ({
    name: s.name,
    type: 'line',
    data: s.values,
    symbol: 'none',
    lineStyle: { width: 2 },
    color: colors[i % colors.length],
  })),
}))
</script>

<template>
  <v-chart :option="option" autoresize style="height: 360px; width: 100%" />
</template>
