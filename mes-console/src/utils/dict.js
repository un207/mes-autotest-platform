/**
 * 共用字典与格式化。
 *
 * 为什么集中在一处：状态英文码（NEW / DISPATCHED / …）在列表、详情、标签、筛选项里到处出现。
 * 如果每处各写一份中文映射，改一处漏一处，界面就会出现"同一状态两种叫法"。
 * 这里作为唯一来源，页面只引用不重定义。
 *
 * 取值口径与后端枚举严格一致（mes-platform 的 OrderStatus / InspectType / MetricType 等）。
 */

// ---------------------------------------------------------------- 工单状态
export const ORDER_STATUS = {
  NEW: { label: '新建', type: 'info' },
  DISPATCHED: { label: '已派工', type: 'primary' },
  IN_PROGRESS: { label: '生产中', type: 'warning' },
  CLOSED: { label: '已关闭', type: 'success' }
}

export const ORDER_STATUS_OPTIONS = Object.entries(ORDER_STATUS).map(([value, v]) => ({
  value,
  label: v.label
}))

// ---------------------------------------------------------------- 检验类型
export const INSPECT_TYPE = {
  IQC: '来料检验',
  IPQC: '过程检验',
  FQC: '完工检验',
  OQC: '出货检验'
}

export const INSPECT_TYPE_OPTIONS = Object.entries(INSPECT_TYPE).map(([value, label]) => ({
  value,
  label
}))

// ---------------------------------------------------------------- 检验结论
export const INSPECT_RESULT = {
  PASS: { label: '合格', type: 'success' },
  FAIL: { label: '不合格', type: 'danger' }
}

// ---------------------------------------------------------------- 批次状态
export const BATCH_STATUS = {
  IN_STOCK: { label: '在库', type: 'info' },
  IN_USE: { label: '在用', type: 'primary' },
  CONSUMED: { label: '已消耗', type: 'success' },
  FROZEN: { label: '冻结', type: 'warning' }
}

export const BATCH_STATUS_OPTIONS = Object.entries(BATCH_STATUS).map(([value, v]) => ({
  value,
  label: v.label
}))

// ---------------------------------------------------------------- 追溯节点
export const TRACE_NODE = {
  INBOUND: { label: '来料入库', type: 'info' },
  PRODUCE: { label: '投产报工', type: 'primary' },
  INSPECT: { label: '质量检验', type: 'warning' },
  OUTBOUND: { label: '出货消耗', type: 'success' }
}

// ---------------------------------------------------------------- 数采指标
export const METRIC = {
  OUTPUT: { label: '产量', unit: '件' },
  STATUS: { label: '运行状态', unit: '' },
  TEMPERATURE: { label: '温度', unit: '℃' }
}

export const METRIC_OPTIONS = Object.entries(METRIC).map(([value, v]) => ({
  value,
  label: v.label
}))

// ---------------------------------------------------------------- 数据质量
export const QUALITY_FLAG = {
  OK: { label: '正常', type: 'success' },
  SUSPECT: { label: '可疑', type: 'warning' },
  BAD: { label: '异常', type: 'danger' }
}

export const QUALITY_FLAG_OPTIONS = Object.entries(QUALITY_FLAG).map(([value, v]) => ({
  value,
  label: v.label
}))

// ---------------------------------------------------------------- 通用取值器
export function dictLabel(dict, code, fallback = '—') {
  const hit = dict[code]
  if (!hit) return code || fallback
  return typeof hit === 'string' ? hit : hit.label
}

export function dictType(dict, code) {
  const hit = dict[code]
  return hit && typeof hit === 'object' ? hit.type : 'info'
}

/** 运行状态码：设备侧专用（0 停机 / 1 运行 / 2 故障） */
export function runStatusLabel(code) {
  return { 0: '停机', 1: '运行', 2: '故障' }[code] ?? `未知(${code})`
}

export function runStatusType(code) {
  return { 0: 'info', 1: 'success', 2: 'danger' }[code] ?? 'info'
}

// ---------------------------------------------------------------- 格式化
/** 保留 n 位小数并按需补零；非数值原样返回 '—' */
export function num(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (Number.isNaN(n)) return String(value)
  return digits === 0 ? String(Math.round(n)) : n.toFixed(digits)
}

/** 良率/进度这类百分比，undefined 时不显示 0 以免误导 */
export function percent(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '—'
  return `${num(value, digits)}%`
}

/**
 * 良率的语义色：< 90% 红、< 97% 黄、其余绿。
 * 阈值按制造现场的一般经验，集中在函数里，改口径只改这里。
 */
export function rateClass(rate) {
  if (rate === null || rate === undefined) return ''
  const r = Number(rate)
  if (Number.isNaN(r)) return ''
  if (r < 90) return 'is-bad'
  if (r < 97) return 'is-warn'
  return 'is-good'
}

export function qualityFlagType(flag) {
  return dictType(QUALITY_FLAG, flag)
}

export function qualityFlagLabel(flag) {
  return dictLabel(QUALITY_FLAG, flag)
}

// ---------------------------------------------------------------- 时间
/** 后端返回 'yyyy-MM-dd HH:mm:ss'，直接展示即可；这里只做空值兜底 */
export function datetime(value) {
  return value || '—'
}

/** 今天日期的 yyyy-MM-dd，用于给日期选择器设默认值 */
export function today() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** 从今天往前推 n 天 */
export function daysAgo(n) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  const p = (x) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
