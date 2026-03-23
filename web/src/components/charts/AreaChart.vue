<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart as LineChartType } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  DataZoomComponent,
  VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChartType, TitleComponent, TooltipComponent, GridComponent, DataZoomComponent, VisualMapComponent, CanvasRenderer])

const props = withDefaults(
  defineProps<{
    dates: string[]
    values: number[]
    title?: string
    color?: string
  }>(),
  {
    title: '',
    color: '#F56C6C',
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
    formatter(params: any[]) {
      const p = params[0]
      return `<div style="font-weight:600">${p.axisValueLabel}</div>
              <div>${p.marker} ${(p.value as number).toFixed(2)}%</div>`
    },
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
    data: props.dates,
    axisLabel: { fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    axisLabel: {
      fontSize: 11,
      formatter: '{value}%',
    },
  },
  dataZoom: [
    { type: 'inside', start: 0, end: 100 },
    { type: 'slider', start: 0, end: 100, height: 20, bottom: 24 },
  ],
  series: [
    {
      type: 'line',
      data: props.values,
      symbol: 'none',
      lineStyle: { width: 1.5, color: props.color },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: props.color + '80' },
            { offset: 1, color: props.color + '10' },
          ],
        },
      },
      itemStyle: { color: props.color },
    },
  ],
}))
</script>

<template>
  <v-chart :option="option" autoresize style="height: 300px; width: 100%" />
</template>
