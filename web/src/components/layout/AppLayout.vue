<script setup lang="ts">
import { ref } from 'vue'
import Sidebar from './Sidebar.vue'

const collapsed = ref(false)

function toggleSidebar() {
  collapsed.value = !collapsed.value
}
</script>

<template>
  <el-container class="app-layout">
    <el-aside :width="collapsed ? '64px' : '220px'" class="app-aside">
      <Sidebar :collapsed="collapsed" @toggle="toggleSidebar" />
    </el-aside>
    <el-container direction="vertical">
      <el-header class="app-header">
        <span class="header-title">基金量化分析系统</span>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped lang="scss">
.app-layout {
  height: 100vh;
}

.app-aside {
  transition: width 0.3s ease;
  overflow: hidden;
}

.app-header {
  height: $header-height;
  display: flex;
  align-items: center;
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  padding: 0 20px;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
}

.app-main {
  padding: 20px;
  background-color: $bg-color;
  overflow-y: auto;
}
</style>
