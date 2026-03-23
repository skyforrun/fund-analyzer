import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  getDipPlans,
  getDipDue,
  createDipPlan,
  pauseDipPlan,
  resumeDipPlan,
  stopDipPlan,
} from '@/api/dip'
import type { DipPlanItem, DipDueItem, DipPlanCreate } from '@/types/dip'

export const useDipStore = defineStore('dip', () => {
  const plans = ref<DipPlanItem[]>([])
  const dueItems = ref<DipDueItem[]>([])
  const plansLoading = ref(false)
  const dueLoading = ref(false)

  async function fetchPlans() {
    plansLoading.value = true
    try {
      const res = await getDipPlans()
      plans.value = res.data ?? []
    } catch {
      // 错误已在拦截器中处理
    } finally {
      plansLoading.value = false
    }
  }

  async function fetchDue() {
    dueLoading.value = true
    try {
      const res = await getDipDue()
      dueItems.value = res.data ?? []
    } catch {
      // 错误已在拦截器中处理
    } finally {
      dueLoading.value = false
    }
  }

  async function addPlan(data: DipPlanCreate) {
    await createDipPlan(data)
  }

  async function pause(id: number) {
    await pauseDipPlan(id)
  }

  async function resume(id: number) {
    await resumeDipPlan(id)
  }

  async function stop(id: number) {
    await stopDipPlan(id)
  }

  return {
    plans,
    dueItems,
    plansLoading,
    dueLoading,
    fetchPlans,
    fetchDue,
    addPlan,
    pause,
    resume,
    stop,
  }
})
