/** 问卷选项 */
export interface QuestionOption {
  label: string
  score: number
}

/** 问卷问题 */
export interface Question {
  id: string
  text: string
  options: QuestionOption[]
}

/** 风险评估档案 */
export interface RiskProfile {
  id: number | null
  risk_level: number
  risk_label: string
  core_ratio: number
  satellite_ratio: number
  assessment_date: string
  answers: Record<string, number> | null
}
