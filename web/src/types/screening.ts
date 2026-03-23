export interface ScreenRequest {
  position_type: string
  top_n: number
}

export interface ScreenResultItem {
  fund_code: string
  fund_name: string | null
  fund_type: string | null
  score: number
  action: string | null
  confidence: string | null
  reason: string | null
}

export interface FeeScheduleItem {
  fee_type: string
  min_holding_days: number
  max_holding_days: number
  fee_rate: number
  min_amount: number
  max_amount: number | null
}
