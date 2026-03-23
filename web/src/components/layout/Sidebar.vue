<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

defineProps<{
  collapsed: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle'): void
}>()

const route = useRoute()
const router = useRouter()

// 从路由配置中获取菜单项（排除重定向路由）
const menuItems = computed(() =>
  router.getRoutes()
    .filter((r) => r.meta?.title && r.meta?.icon)
    .map((r) => ({
      path: r.path,
      title: r.meta!.title as string,
      icon: r.meta!.icon as string,
    }))
)

const activeMenu = computed(() => route.path)
</script>

<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <span v-show="!collapsed" class="sidebar-title">基金分析系统</span>
      <span v-show="collapsed" class="sidebar-title-short">FA</span>
    </div>
    <el-menu
      :default-active="activeMenu"
      :collapse="collapsed"
      router
      class="sidebar-menu"
      background-color="#304156"
      text-color="#bfcbd9"
      active-text-color="#409eff"
    >
      <el-menu-item
        v-for="item in menuItems"
        :key="item.path"
        :index="item.path"
      >
        <el-icon>
          <component :is="item.icon" />
        </el-icon>
        <template #title>{{ item.title }}</template>
      </el-menu-item>
    </el-menu>
    <div class="sidebar-footer">
      <el-button
        :icon="collapsed ? 'Expand' : 'Fold'"
        text
        @click="emit('toggle')"
        style="color: #bfcbd9; width: 100%"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #304156;
}

.sidebar-header {
  height: $header-height;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.sidebar-title-short {
  font-size: 20px;
  font-weight: 700;
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  overflow-y: auto;
}

.sidebar-footer {
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  padding: 8px;
}

// 覆盖 Element Plus 菜单样式
:deep(.el-menu) {
  border-right: none;
}
</style>
