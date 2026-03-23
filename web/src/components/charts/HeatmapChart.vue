<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { HeatmapChart as HeatmapChartType } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([HeatmapChartType, TitleComponent, TooltipComponent, GridComponent, VisualMapComponent, CanvasRenderer])

const props = withDefaults(
  defineProps<{
    dates: string[]
    values: number[]
    title?: string
  }>(),
  {
    title: '',
  },
)

const months = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

/** 将日度收益率转换为月度收益率，再组织成年×月热力图数据 */
const heatmapData = computed(() => {
  if (!props.dates.length) return { years: [] as string[], data: [] as [number, number, number | null][] }

  // 按年-月分组，计算 (1+r1)*(1+r2)*...*(1+rn)-1
  const monthlyMap = new Map<string, number>()
  for (let i = 0; i < props.dates.length; i++) {
    const ym = props.dates[i].substring(0, 7) // yyyy-MM
    const prev = monthlyMap.get(ym)
    const factor = 1 + props.values[i]
    monthlyMap.set(ym, prev !== undefined ? prev * factor : factor)
  }

  // 收集所有年份
  const yearSet = new Set<string>()
  for (const ym of monthlyMap.keys()) {
    yearSet.add(ym.substring(0, 4))
  }
  const years = Array.from(yearSet).sort()

  // 构建热力图数据: [monthIndex, yearIndex, returnPct]
  const data: [number, number, number | null][] = []
  for (let yi = 0; yi < years.length; yi++) {
    for (let mi = 0; mi < 12; mi++) {
      const ym = `${years[yi]}-${String(mi + 1).padStart(2, '0')}`
      const factor = monthlyMap.get(ym)
      if (factor !== undefined) {
        data.push([mi, yi, Number(((factor - 1) * 100).toFixed(2))])
      } else {
        data.push([mi, yi, null])
      }
    }
  }

  return { years, data }
})

const option = computed(() => {
  const { years, data } = heatmapData.value
  const allVals = data.map((d) => d[2]).filter((v): v is number => v !== null)
  const minVal = allVals.length ? Math.min(...allVals) : -10
  const maxVal = allVals.length ? Math.max(...allVals) : 10

  return {
    title: props.title
      ? {
          text: props.title,
          left: 'center',
          textStyle: { fontSize: 14, fontWeight: 600 },
        }
      : undefined,
    tooltip: {
      formatter(params: any) {
        const [mi, yi, val] = params.data
        if (val === null) return ''
        return `${years[yi]}年${months[mi]}<br/>收益率: ${val > 0 ? '+' : ''}${val}%`
      },
    },
    grid: {
      left: '12%',
      right: '8%',
      bottom: 40,
      top: props.title ? 40 : 20,
    },
    xAxis: {
      type: 'category',
      data: months,
      splitArea: { show: true },
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'category',
      data: years,
      splitArea: { show: true },
      axisLabel: { fontSize: 11 },
    },
    visualMap: {
      min: minVal,
      max: maxVal,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: {
        color: ['#c0392b', '#e74c3c', '#f5f5f5', '#27ae60', '#1e8449'],
      },
      textStyle: { fontSize: 11 },
      formatter: (value: number) => `${value.toFixed(1)}%`,
    },
    series: [
      {
        type: 'heatmap',
        data: data.filter((d) => d[2] !== null),
        label: {
          show: true,
          fontSize: 10,
          formatter: (params: any) => {
            const val = params.data[2]
            return val !== null ? `${val > 0 ? '+' : ''}${val}%` : ''
          },
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
      },
    ],
  }
})
</script>

<template>
  <v-chart :option="option" autoresize style="height: 320px; width: 100%" />
</template>
