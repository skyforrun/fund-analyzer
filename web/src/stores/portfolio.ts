import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  getPortfolioSummary,
  getPortfolioHoldings,
  buyFund,
  sellFund,
  getDividends,
  getFeeRates,
} from '@/api/portfolio'
import type { DashboardSummary } from '@/types/dashboard'
import type { PortfolioHoldingItem, BuyRequest, SellRequest, DividendItem, FeeRateItem } from '@/types/portfolio'

export const usePortfolioStore = defineStore('portfolio', () => {
  const summary = ref<DashboardSummary | null>(null)
  const holdings = ref<PortfolioHoldingItem[]>([])
  const dividends = ref<DividendItem[]>([])
  const feeRates = ref<FeeRateItem[]>([])
  const summaryLoading = ref(false)
  const holdingsLoading = ref(false)
  const dividendsLoading = ref(false)
  const feeRatesLoading = ref(false)

  async function fetchSummary() {
    summaryLoading.value = true
    try {
      const res = await getPortfolioSummary()
      summary.value = res.data
    } catch {
      // 错误已在拦截器中处理
    } finally {
      summaryLoading.value = false
    }
  }

  async function fetchHoldings() {
    holdingsLoading.value = true
    try {
      const res = await getPortfolioHoldings()
      holdings.value = res.data ?? []
    } catch {
      // 错误已在拦截器中处理
    } finally {
      holdingsLoading.value = false
    }
  }

  async function executeBuy(data: BuyRequest) {
    await buyFund(data)
  }

  async function executeSell(data: SellRequest) {
    await sellFund(data)
  }

  async function fetchDividends() {
    dividendsLoading.value = true
    try {
      const res = await getDividends()
      dividends.value = res.data ?? []
    } catch {
      // 错误已在拦截器中处理
    } finally {
      dividendsLoading.value = false
    }
  }

  async function fetchFeeRates() {
    feeRatesLoading.value = true
    try {
      const res = await getFeeRates()
      feeRates.value = res.data ?? []
    } catch {
      // 错误已在拦截器中处理
    } finally {
      feeRatesLoading.value = false
    }
  }

  return {
    summary,
    holdings,
    dividends,
    feeRates,
    summaryLoading,
    holdingsLoading,
    dividendsLoading,
    feeRatesLoading,
    fetchSummary,
    fetchHoldings,
    executeBuy,
    executeSell,
    fetchDividends,
    fetchFeeRates,
  }
})
