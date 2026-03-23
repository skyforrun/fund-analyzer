import request from './request'
import type { ApiResponse } from '@/types'
import type { RebalanceResult } from '@/types/rebalance'

/** 生成调仓建议 */
export function generateRebalance() {
  return request.post<any, ApiResponse<RebalanceResult>>('/rebalance/generate')
}
