import request from './request'
import type { ApiResponse } from '@/types'
import type { DipPlanItem, DipDueItem, DipPlanCreate } from '@/types/dip'

/** 获取定投计划列表 */
export function getDipPlans() {
  return request.get<any, ApiResponse<DipPlanItem[]>>('/dip/plans')
}

/** 获取到期提醒 */
export function getDipDue() {
  return request.get<any, ApiResponse<DipDueItem[]>>('/dip/due')
}

/** 新建定投计划 */
export function createDipPlan(data: DipPlanCreate) {
  return request.post<any, ApiResponse<DipPlanItem>>('/dip/plans', data)
}

/** 暂停定投计划 */
export function pauseDipPlan(id: number) {
  return request.post<any, ApiResponse<null>>(`/dip/plans/${id}/pause`)
}

/** 恢复定投计划 */
export function resumeDipPlan(id: number) {
  return request.post<any, ApiResponse<null>>(`/dip/plans/${id}/resume`)
}

/** 停止定投计划 */
export function stopDipPlan(id: number) {
  return request.post<any, ApiResponse<null>>(`/dip/plans/${id}/stop`)
}
