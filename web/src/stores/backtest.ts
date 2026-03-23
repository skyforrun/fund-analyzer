import { defineStore } from 'pinia'
import { ref } from 'vue'
import { postBacktestRun } from '@/api/backtest'
import type { BacktestRequest, BacktestResult } from '@/types/backtest'

export const useBacktestStore = defineStore('backtest', () => {
  const result = ref<BacktestResult | null>(null)
  const loading = ref(false)

  async function runBacktest(params: BacktestRequest) {
    loading.value = true
    try {
      const res = await postBacktestRun(params)
      result.value = res.data ?? null
    } catch {
      // 错误已在拦截器中处理
    } finally {
      loading.value = false
    }
  }

  return {
    result,
    loading,
    runBacktest,
  }
})
