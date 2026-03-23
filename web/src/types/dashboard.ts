/** 持仓明细 */
export interface HoldingItem {
  fund_code: string
  fund_name: string
  position_type: '核心' | '卫星'
  shares: number
  cost_price: number
  current_nav: number
  market_value: number
  pnl: number
  return_pct: number
}

/** 按类型汇总 */
export interface TypeSummary {
  position_type: string
  market_value: number
  ratio: number
}

/** 仪表盘摘要数据 */
export interface DashboardSummary {
  total_market_value: number
  total_cost: number
  total_pnl: number
  total_return_pct: number
  type_summary: TypeSummary[]
  holdings: HoldingItem[]
}

/** 估值条目 */
export interface EstimateItem {
  fund_code: string
  fund_name: string
  estimate_nav: number
  estimate_change_pct: number
  estimate_time: string
}
