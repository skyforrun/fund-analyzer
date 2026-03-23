import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '仪表盘', icon: 'Odometer' },
  },
  {
    path: '/screening',
    name: 'Screening',
    component: () => import('@/views/Screening.vue'),
    meta: { title: '基金筛选', icon: 'Search' },
  },
  {
    path: '/watchlist',
    name: 'Watchlist',
    component: () => import('@/views/Watchlist.vue'),
    meta: { title: '自选基金', icon: 'Star' },
  },
  {
    path: '/backtest',
    name: 'Backtest',
    component: () => import('@/views/Backtest.vue'),
    meta: { title: '回测分析', icon: 'TrendCharts' },
  },
  {
    path: '/portfolio',
    name: 'Portfolio',
    component: () => import('@/views/Portfolio.vue'),
    meta: { title: '持仓管理', icon: 'Wallet' },
  },
  {
    path: '/dip',
    name: 'DipPlan',
    component: () => import('@/views/DipPlan.vue'),
    meta: { title: '定投计划', icon: 'Timer' },
  },
  {
    path: '/rebalance',
    name: 'Rebalance',
    component: () => import('@/views/Rebalance.vue'),
    meta: { title: '调仓建议', icon: 'Refresh' },
  },
  {
    path: '/risk',
    name: 'RiskAssess',
    component: () => import('@/views/RiskAssess.vue'),
    meta: { title: '风险评估', icon: 'Warning' },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
    meta: { title: '系统设置', icon: 'Setting' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：设置页面标题
router.beforeEach((to, _from, next) => {
  const title = (to.meta?.title as string) || '基金量化分析系统'
  document.title = `${title} - 基金量化分析系统`
  next()
})

export default router
