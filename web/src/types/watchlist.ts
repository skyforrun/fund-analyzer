/** 自选基金项 */
export interface WatchlistItem {
  id: number
  fund_code: string
  fund_name: string | null
  group_name: string
  notes: string | null
  added_at: string | null
}

/** 创建自选基金请求 */
export interface WatchlistCreateRequest {
  fund_code: string
  fund_name?: string
  group_name?: string
  notes?: string
}
