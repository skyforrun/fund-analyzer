import request from './request'
import type { ApiResponse } from '@/types'
import type { Question, RiskProfile } from '@/types/risk'

/** 获取风险评估问卷 */
export function getRiskQuestions() {
  return request.get<any, ApiResponse<Question[]>>('/risk/questions')
}

/** 获取当前风险档案 */
export function getRiskProfile() {
  return request.get<any, ApiResponse<RiskProfile | null>>('/risk/profile')
}

/** 提交风险评估 */
export function submitRiskAssess(answers: Record<string, number>) {
  return request.post<any, ApiResponse<RiskProfile>>('/risk/assess', { answers })
}
