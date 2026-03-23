<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart as PieChartType } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([PieChartType, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  title: string
  data: Array<{ name: string; value: number }>
}>()

const option = computed(() => ({
  title: {
    text: props.title,
    left: 'center',
    textStyle: { fontSize: 14, fontWeight: 600 },
  },
  tooltip: {
    trigger: 'item',
    formatter: '{b}: ¥{c} ({d}%)',
  },
  legend: {
    orient: 'horizontal',
    bottom: 0,
  },
  series: [
    {
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 6,
        borderColor: '#fff',
        borderWidth: 2,
      },
      label: {
        show: true,
        formatter: '{b}\n{d}%',
      },
      data: props.data,
    },
  ],
}))
</script>

<template>
  <v-chart :option="option" autoresize style="height: 300px; width: 100%" />
</template>
