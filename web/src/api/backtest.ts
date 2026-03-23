import request from './request'
import type { ApiResponse } from '@/types'
import type { BacktestRequest, BacktestResult } from '@/types/backtest'

/** 运行回测 */
export function postBacktestRun(data: BacktestRequest) {
  return request.post<any, ApiResponse<BacktestResult>>('/backtest/run', data)
}
