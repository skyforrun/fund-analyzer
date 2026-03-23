import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getDashboardSummary, getDashboardEstimates } from '@/api/dashboard'
import type { DashboardSummary, EstimateItem } from '@/types/dashboard'

export const useDashboardStore = defineStore('dashboard', () => {
  const summary = ref<DashboardSummary | null>(null)
  const estimates = ref<EstimateItem[]>([])
  const summaryLoading = ref(false)
  const estimatesLoading = ref(false)

  async function fetchSummary() {
    summaryLoading.value = true
    try {
      const res = await getDashboardSummary()
      summary.value = res.data
    } catch {
      // 错误已在拦截器中处理
    } finally {
      summaryLoading.value = false
    }
  }

  async function fetchEstimates() {
    estimatesLoading.value = true
    try {
      const res = await getDashboardEstimates()
      estimates.value = res.data ?? []
    } catch {
      // 错误已在拦截器中处理
    } finally {
      estimatesLoading.value = false
    }
  }

  return {
    summary,
    estimates,
    summaryLoading,
    estimatesLoading,
    fetchSummary,
    fetchEstimates,
  }
})
