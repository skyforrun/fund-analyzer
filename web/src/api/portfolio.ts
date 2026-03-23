import request from './request'
import type { ApiResponse } from '@/types'
import type { DashboardSummary } from '@/types/dashboard'
import type { PortfolioHoldingItem, BuyRequest, SellRequest, DividendItem, FeeRateItem } from '@/types/portfolio'

/** 获取持仓摘要 */
export function getPortfolioSummary() {
  return request.get<any, ApiResponse<DashboardSummary>>('/portfolio/summary')
}

/** 获取持仓明细 */
export function getPortfolioHoldings() {
  return request.get<any, ApiResponse<PortfolioHoldingItem[]>>('/portfolio/holdings')
}

/** 买入 */
export function buyFund(data: BuyRequest) {
  return request.post<any, ApiResponse<null>>('/portfolio/buy', data)
}

/** 卖出 */
export function sellFund(data: SellRequest) {
  return request.post<any, ApiResponse<null>>('/portfolio/sell', data)
}

/** 获取分红记录 */
export function getDividends() {
  return request.get<any, ApiResponse<DividendItem[]>>('/portfolio/dividends')
}

/** 获取赎回费率 */
export function getFeeRates() {
  return request.get<any, ApiResponse<FeeRateItem[]>>('/portfolio/fee-rate')
}
