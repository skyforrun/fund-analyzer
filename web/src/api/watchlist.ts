import request from './request'
import type { ApiResponse } from '@/types'
import type { WatchlistItem, WatchlistCreateRequest } from '@/types/watchlist'

/** 获取自选基金列表 */
export function getWatchlist(groupName?: string) {
  return request.get<any, ApiResponse<WatchlistItem[]>>('/watchlist', {
    params: groupName ? { group_name: groupName } : {},
  })
}

/** 获取分组列表 */
export function getWatchlistGroups() {
  return request.get<any, ApiResponse<string[]>>('/watchlist/groups')
}

/** 添加自选基金 */
export function addWatchlistItem(data: WatchlistCreateRequest) {
  return request.post<any, ApiResponse<WatchlistItem>>('/watchlist', data)
}

/** 删除自选基金 */
export function deleteWatchlistItem(code: string, groupName?: string) {
  return request.delete<any, ApiResponse<number>>(`/watchlist/${code}`, {
    params: groupName ? { group_name: groupName } : {},
  })
}
