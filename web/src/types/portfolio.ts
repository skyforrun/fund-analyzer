/** 持仓明细项 */
export interface PortfolioHoldingItem {
  fund_code: string
  fund_name: string | null
  position_type: string | null
  shares: number
  cost_price: number
  buy_date: string | null
}

/** 买入请求 */
export interface BuyRequest {
  fund_code: string
  amount: number
  nav: number
  position_type: string
}

/** 卖出请求 */
export interface SellRequest {
  fund_code: string
  shares: number
  nav: number
}

/** 分红记录项 */
export interface DividendItem {
  fund_code: string
  ex_date: string
  dividend_per_unit: number | null
  dividend_type: string | null
}

/** 赎回费率项 */
export interface FeeRateItem {
  fund_code: string
  holding_days: number
  fee_rate: number | null
}
