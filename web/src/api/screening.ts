import request from './request'
import type { ApiResponse } from '@/types'
import type { ScreenRequest, ScreenResultItem, FeeScheduleItem } from '@/types/screening'

/** 筛选评分 */
export function postScreeningScore(data: ScreenRequest) {
  return request.post<any, ApiResponse<ScreenResultItem[]>>('/screening/score', data)
}

/** 获取基金费率 */
export function getFundFees(code: string) {
  return request.get<any, ApiResponse<FeeScheduleItem[]>>(`/screening/fees/${code}`)
}
