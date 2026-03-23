export interface BacktestRequest {
  start_date: string
  end_date?: string
  initial_capital: number
  core_ratio: number
  benchmark_code: string
}

export interface SeriesData {
  dates: string[]
  values: number[]
}

export interface BacktestMetrics {
  annualized_return: number
  annualized_volatility: number
  max_drawdown: number
  sharpe_ratio: number
  sortino_ratio: number
  calmar_ratio: number
  monthly_win_rate: number
  information_ratio: number | null
  alpha: number | null
}

export interface BacktestResult {
  portfolio_returns: SeriesData
  benchmark_returns: SeriesData
  portfolio_values: SeriesData
  metrics: BacktestMetrics
  total_fees_paid: number
  final_value: number
  initial_capital: number
}
