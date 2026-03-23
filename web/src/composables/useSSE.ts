import { ref } from 'vue'

export function useSSE(url: string) {
  const progress = ref(0)
  const message = ref('')
  const done = ref(false)
  const result = ref<any>(null)

  function start() {
    done.value = false
    progress.value = 0
    message.value = ''
    result.value = null

    const source = new EventSource(url)

    source.addEventListener('progress', (e: MessageEvent) => {
      const data = JSON.parse(e.data)
      progress.value = data.total > 0 ? Math.round(data.current / data.total * 100) : 0
      message.value = data.message
    })

    source.addEventListener('done', (e: MessageEvent) => {
      result.value = JSON.parse(e.data)
      done.value = true
      source.close()
    })

    source.addEventListener('error', () => {
      source.close()
    })
  }

  return { progress, message, done, result, start }
}
