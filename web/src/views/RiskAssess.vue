<script setup lang="ts">
import { onMounted, ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { getRiskQuestions, getRiskProfile, submitRiskAssess } from '@/api/risk'
import { formatPercent } from '@/composables/useDecimal'
import type { Question, RiskProfile } from '@/types/risk'

const questions = ref<Question[]>([])
const profile = ref<RiskProfile | null>(null)
const answers = reactive<Record<string, number>>({})
const questionsLoading = ref(false)
const profileLoading = ref(false)
const submitLoading = ref(false)

function riskLevelType(level: number) {
  if (level <= 2) return 'success'
  if (level <= 3) return 'warning'
  return 'danger'
}

async function fetchQuestions() {
  questionsLoading.value = true
  try {
    const res = await getRiskQuestions()
    questions.value = res.data ?? []
    // 初始化 answers
    for (const q of questions.value) {
      if (!(q.id in answers)) {
        answers[q.id] = q.options[0]?.score ?? 0
      }
    }
  } catch {
    // 错误已在拦截器中处理
  } finally {
    questionsLoading.value = false
  }
}

async function fetchProfile() {
  profileLoading.value = true
  try {
    const res = await getRiskProfile()
    profile.value = res.data ?? null
  } catch {
    // 错误已在拦截器中处理
  } finally {
    profileLoading.value = false
  }
}

async function handleSubmit() {
  submitLoading.value = true
  try {
    const res = await submitRiskAssess({ ...answers })
    profile.value = res.data
    ElMessage.success('风险评估完成')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    submitLoading.value = false
  }
}

onMounted(() => {
  fetchProfile()
  fetchQuestions()
})
</script>

<template>
  <div class="risk-page">
    <!-- 当前评估结果 -->
    <el-card shadow="hover" class="section-card" v-loading="profileLoading">
      <template #header>
        <span class="card-title">当前评估结果</span>
      </template>
      <template v-if="profile">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="风险等级">
            <el-tag :type="riskLevelType(profile.risk_level)" size="default">
              {{ profile.risk_level }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="风险标签">
            {{ profile.risk_label }}
          </el-descriptions-item>
          <el-descriptions-item label="核心仓占比">
            {{ formatPercent(profile.core_ratio * 100) }}%
          </el-descriptions-item>
          <el-descriptions-item label="卫星仓占比">
            {{ formatPercent(profile.satellite_ratio * 100) }}%
          </el-descriptions-item>
          <el-descriptions-item label="评估日期">
            {{ profile.assessment_date }}
          </el-descriptions-item>
        </el-descriptions>
      </template>
      <el-empty v-else description="暂无评估结果，请填写下方问卷" />
    </el-card>

    <!-- 问卷表单 -->
    <el-card shadow="hover" class="section-card" v-loading="questionsLoading">
      <template #header>
        <span class="card-title">风险评估问卷</span>
      </template>
      <el-form label-position="top" v-if="questions.length > 0">
        <el-form-item
          v-for="(q, index) in questions"
          :key="q.id"
          :label="`${index + 1}. ${q.text}`"
        >
          <el-radio-group v-model="answers[q.id]">
            <el-radio
              v-for="opt in q.options"
              :key="opt.score"
              :value="opt.score"
              style="display: block; margin-bottom: 8px"
            >
              {{ opt.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
            提交评估
          </el-button>
        </el-form-item>
      </el-form>
      <el-empty v-else description="暂无评估问卷" />
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.risk-page {
  max-width: 1000px;
}

.section-card {
  margin-bottom: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}
</style>
