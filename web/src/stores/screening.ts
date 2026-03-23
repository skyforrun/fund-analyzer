import { defineStore } from 'pinia'
import { ref } from 'vue'
import { postScreeningScore, getFundFees } from '@/api/screening'
import type { ScreenResultItem, FeeScheduleItem } from '@/types/screening'

export const useScreeningStore = defineStore('screening', () => {
  const results = ref<ScreenResultItem[]>([])
  const loading = ref(false)
  const fees = ref<FeeScheduleItem[]>([])
  const feesLoading = ref(false)

  async function fetchScore(positionType: string, topN: number) {
    loading.value = true
    try {
      const res = await postScreeningScore({ position_type: positionType, top_n: topN })
      results.value = res.data ?? []
    } catch {
      // 错误已在拦截器中处理
    } finally {
      loading.value = false
    }
  }

  async function fetchFees(code: string) {
    feesLoading.value = true
    try {
      const res = await getFundFees(code)
      fees.value = res.data ?? []
    } catch {
      // 错误已在拦截器中处理
    } finally {
      feesLoading.value = false
    }
  }

  return {
    results,
    loading,
    fees,
    feesLoading,
    fetchScore,
    fetchFees,
  }
})
