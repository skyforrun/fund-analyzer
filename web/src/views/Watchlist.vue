<script setup lang="ts">
import { onMounted, ref, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useWatchlistStore } from '@/stores/watchlist'
import type { WatchlistCreateRequest } from '@/types/watchlist'
import type { FormInstance } from 'element-plus'

const store = useWatchlistStore()

// 当前选中的分组
const selectedGroup = ref<string>('')

// 分组切换
function handleGroupChange(val: string) {
  selectedGroup.value = val
  store.fetchItems(val || undefined)
}

// 添加对话框
const dialogVisible = ref(false)
const addFormRef = ref<FormInstance>()
const addForm = reactive<WatchlistCreateRequest>({
  fund_code: '',
  fund_name: '',
  group_name: '',
  notes: '',
})
const addLoading = ref(false)

const addRules = {
  fund_code: [{ required: true, message: '请输入基金代码', trigger: 'blur' }],
}

function openAddDialog() {
  dialogVisible.value = true
}

async function handleAdd() {
  const valid = await addFormRef.value?.validate().catch(() => false)
  if (!valid) return
  addLoading.value = true
  try {
    await store.addItem({ ...addForm })
    ElMessage.success('添加成功')
    dialogVisible.value = false
    addFormRef.value?.resetFields()
    store.fetchItems(selectedGroup.value || undefined)
    store.fetchGroups()
  } catch {
    // 错误已在拦截器中处理
  } finally {
    addLoading.value = false
  }
}

function handleDialogClose() {
  addFormRef.value?.resetFields()
}

// 删除
async function handleDelete(code: string, groupName: string) {
  try {
    await ElMessageBox.confirm(`确定要删除基金 ${code} 吗？`, '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await store.removeItem(code, groupName || undefined)
    ElMessage.success('删除成功')
    store.fetchItems(selectedGroup.value || undefined)
  } catch (e: any) {
    // 取消操作或错误已在拦截器中处理
    if (e !== 'cancel' && e?.toString() !== 'cancel') {
      // 非用户取消的错误
    }
  }
}

onMounted(() => {
  store.fetchItems()
  store.fetchGroups()
})
</script>

<template>
  <div class="watchlist-page">
    <!-- 工具栏 -->
    <el-card shadow="hover" class="toolbar-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <span class="toolbar-label">分组筛选：</span>
          <el-select
            v-model="selectedGroup"
            placeholder="全部分组"
            clearable
            style="width: 200px"
            @change="handleGroupChange"
            :loading="store.groupsLoading"
          >
            <el-option v-for="g in store.groups" :key="g" :label="g" :value="g" />
          </el-select>
        </div>
        <el-button type="primary" @click="openAddDialog">
          <el-icon><Plus /></el-icon> 添加自选
        </el-button>
      </div>
    </el-card>

    <!-- 自选列表 -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <span class="card-title">自选列表</span>
      </template>
      <el-table
        :data="store.items"
        stripe
        v-loading="store.loading"
        empty-text="暂无自选基金"
        style="width: 100%"
      >
        <el-table-column prop="fund_code" label="基金代码" width="120" />
        <el-table-column prop="fund_name" label="基金名称" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.fund_name ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="group_name" label="分组" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ row.group_name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.notes ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="added_at" label="添加时间" width="180">
          <template #default="{ row }">{{ row.added_at ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              type="danger"
              text
              size="small"
              @click="handleDelete(row.fund_code, row.group_name)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加对话框 -->
    <el-dialog
      v-model="dialogVisible"
      title="添加自选基金"
      width="480px"
      @close="handleDialogClose"
    >
      <el-form
        ref="addFormRef"
        :model="addForm"
        :rules="addRules"
        label-width="80px"
        label-position="left"
      >
        <el-form-item label="基金代码" prop="fund_code">
          <el-input v-model="addForm.fund_code" placeholder="如 000001" />
        </el-form-item>
        <el-form-item label="基金名称" prop="fund_name">
          <el-input v-model="addForm.fund_name" placeholder="可选" />
        </el-form-item>
        <el-form-item label="分组" prop="group_name">
          <el-select
            v-model="addForm.group_name"
            filterable
            allow-create
            placeholder="选择或新建分组"
            style="width: 100%"
          >
            <el-option v-for="g in store.groups" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注" prop="notes">
          <el-input v-model="addForm.notes" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="addLoading" @click="handleAdd">确认添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.watchlist-page {
  max-width: 1400px;
}

.toolbar-card {
  margin-bottom: 16px;

  :deep(.el-card__body) {
    padding: 12px 20px;
  }
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.toolbar-label {
  font-size: 14px;
  color: #606266;
  margin-right: 8px;
}

.section-card {
  margin-bottom: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}
</style>
