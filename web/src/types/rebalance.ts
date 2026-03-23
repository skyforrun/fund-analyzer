/** 调仓行动项 */
export interface ActionItem {
  fund_code: string
  position_type: string
  action: string
  reason: string
}

/** 调仓结果 */
export interface RebalanceResult {
  as_of: string
  actions: ActionItem[]
  core_picks: [string, number][]
  satellite_picks: [string, number][]
}
