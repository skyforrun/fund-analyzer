import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getWatchlist, getWatchlistGroups, addWatchlistItem, deleteWatchlistItem } from '@/api/watchlist'
import type { WatchlistItem, WatchlistCreateRequest } from '@/types/watchlist'

export const useWatchlistStore = defineStore('watchlist', () => {
  const items = ref<WatchlistItem[]>([])
  const groups = ref<string[]>([])
  const loading = ref(false)
  const groupsLoading = ref(false)

  async function fetchItems(groupName?: string) {
    loading.value = true
    try {
      const res = await getWatchlist(groupName)
      items.value = res.data ?? []
    } catch {
      // 错误已在拦截器中处理
    } finally {
      loading.value = false
    }
  }

  async function fetchGroups() {
    groupsLoading.value = true
    try {
      const res = await getWatchlistGroups()
      groups.value = res.data ?? []
    } catch {
      // 错误已在拦截器中处理
    } finally {
      groupsLoading.value = false
    }
  }

  async function addItem(data: WatchlistCreateRequest) {
    await addWatchlistItem(data)
  }

  async function removeItem(code: string, groupName?: string) {
    await deleteWatchlistItem(code, groupName)
  }

  return {
    items,
    groups,
    loading,
    groupsLoading,
    fetchItems,
    fetchGroups,
    addItem,
    removeItem,
  }
})
