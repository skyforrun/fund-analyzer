/**
 * 数字格式化工具
 */

/** 格式化金额：¥1,234.56 */
export function formatMoney(value: number | undefined | null): string {
  if (value === undefined || value === null) return '¥0.00'
  return `¥${value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

/** 格式化百分比：12.34（不含 % 符号，由调用方添加） */
export function formatPercent(value: number | undefined | null): string {
  if (value === undefined || value === null) return '0.00'
  return value.toFixed(2)
}

/** 格式化数字：1,234 */
export function formatNumber(value: number | undefined | null): string {
  if (value === undefined || value === null) return '0'
  return value.toLocaleString('zh-CN')
}
