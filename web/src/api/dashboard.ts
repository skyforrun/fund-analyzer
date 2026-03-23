import request from './request'
import type { ApiResponse } from '@/types'
import type { DashboardSummary, EstimateItem } from '@/types/dashboard'

/** 获取仪表盘摘要数据 */
export function getDashboardSummary() {
  return request.get<any, ApiResponse<DashboardSummary>>('/dashboard/summary')
}

/** 获取实时估值数据 */
export function getDashboardEstimates() {
  return request.get<any, ApiResponse<EstimateItem[]>>('/dashboard/estimates')
}
