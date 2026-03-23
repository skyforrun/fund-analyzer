import { onMounted, onUnmounted, ref } from 'vue'

/**
 * 轮询 composable
 * 仅在交易时段（工作日 9:30-15:00，中国时区）激活
 */
export function usePolling(fn: () => Promise<void>, interval: number = 30000) {
  const isPolling = ref(false)
  let timer: ReturnType<typeof setInterval> | null = null

  /** 判断当前是否为交易时段 */
  function isTradingHours(): boolean {
    const now = new Date()
    // 使用中国时区偏移 (UTC+8)
    const utcHours = now.getUTCHours()
    const utcMinutes = now.getUTCMinutes()
    const chinaHours = (utcHours + 8) % 24
    const chinaMinutes = utcMinutes
    const chinaDay = now.getUTCDay()

    // 周末不交易
    if (chinaDay === 0 || chinaDay === 6) return false

    // 交易时段：9:30 - 15:00
    const timeInMinutes = chinaHours * 60 + chinaMinutes
    return timeInMinutes >= 9 * 60 + 30 && timeInMinutes <= 15 * 60
  }

  function start() {
    if (timer) return
    isPolling.value = true
    timer = setInterval(async () => {
      if (isTradingHours()) {
        await fn()
      }
    }, interval)
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    isPolling.value = false
  }

  onMounted(() => start())
  onUnmounted(() => stop())

  return { isPolling, start, stop }
}
