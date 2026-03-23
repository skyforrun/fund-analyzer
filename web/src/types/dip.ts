/** 定投计划创建请求 */
export interface DipPlanCreate {
  fund_code: string
  amount: number
  frequency: string
  smart: boolean
}

/** 定投计划项 */
export interface DipPlanItem {
  id: number
  fund_code: string
  amount: number
  frequency: string
  start_date: string | null
  status: string
  smart_dip: boolean | null
}

/** 到期定投项 */
export interface DipDueItem {
  plan_id: number
  fund_code: string
  amount: number
  smart_dip: boolean | null
}
