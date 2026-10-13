<script setup>
/**
 * 工单选择器 —— 用「选」替代「手填工单号」。
 *
 * 工单号形如 WO20261013131408123（20 位），人工既记不住也容易抄错，
 * 因此改为远程搜索选择：输入工单号片段或产品名即时查询，也可直接展开取最近工单。
 *
 * 下拉项同时显示产品名与状态 —— 单看流水号认不出是哪个单，必须带上可辨识信息。
 */
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import api from '../api'
import { ORDER_STATUS, dictLabel, dictType } from '../utils/dict'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '选择工单，可输入单号或产品名搜索' },
  /** 是否可清空。选填场景（如批次建档时绑定工单）需要，必填场景不需要 */
  clearable: { type: Boolean, default: false },
  width: { type: String, default: '320px' },
  /** 禁用某些状态的工单（如追溯只查已投产的单） */
  excludeStatus: { type: Array, default: () => [] }
})

const emit = defineEmits(['update:modelValue', 'change'])

const options = ref([])
const loading = ref(false)
/** 已选中的工单对象。搜索后 options 会被替换，若它不在结果里，
 *  el-select 会退化成只显示号码（丢失产品名），因此单独留存并补回列表 */
const selected = ref(null)

function labelOf(o) {
  return o.productName ? `${o.orderNo} · ${o.productName}` : o.orderNo
}

function filterStatus(records) {
  if (!props.excludeStatus.length) return records
  return records.filter((r) => !props.excludeStatus.includes(r.status))
}

async function fetchOptions(keyword = '') {
  loading.value = true
  try {
    const data = await api.workOrder.page({ pageNum: 1, pageSize: 30, keyword })
    let records = filterStatus(data.records || [])

    // 把当前选中项补进列表，保证回显时仍带产品名与状态
    if (selected.value && !records.some((r) => r.orderNo === selected.value.orderNo)) {
      records = [selected.value, ...records]
    }
    options.value = records
  } catch (err) {
    // 加载失败要显式提示，否则用户面对空下拉不知是「查不到」还是「服务挂了」
    ElMessage.error(`工单列表加载失败：${err.message}`)
    options.value = selected.value ? [selected.value] : []
  } finally {
    loading.value = false
  }
}

function onSearch(keyword) {
  fetchOptions(keyword)
}

function onChange(val) {
  selected.value = options.value.find((o) => o.orderNo === val) || null
  emit('update:modelValue', val)
  emit('change', selected.value)
}

/** 外部传入初始值（或父组件重置表单）时同步内部状态 */
watch(
  () => props.modelValue,
  async (val) => {
    if (!val) {
      selected.value = null
      return
    }
    if (selected.value?.orderNo === val) return

    const hit = options.value.find((o) => o.orderNo === val)
    if (hit) {
      selected.value = hit
      return
    }
    // 不在当前列表里（如父组件回填了历史值），补查一次详情以显示产品名
    try {
      selected.value = await api.workOrder.detail(val)
      if (!options.value.some((o) => o.orderNo === val)) {
        options.value = [selected.value, ...options.value]
      }
    } catch {
      selected.value = { orderNo: val }
    }
  },
  { immediate: true }
)

onMounted(() => fetchOptions())
</script>

<template>
  <el-select
    :model-value="modelValue"
    :placeholder="placeholder"
    :clearable="clearable"
    :loading="loading"
    filterable
    remote
    remote-show-suffix
    :reserve-keyword="false"
    :style="{ width }"
    @search="onSearch"
    @change="onChange"
  >
    <el-option v-for="o in options" :key="o.orderNo" :label="labelOf(o)" :value="o.orderNo">
      <span class="wo-row">
        <span class="mono wo-no">{{ o.orderNo }}</span>
        <span class="wo-name">{{ o.productName || '—' }}</span>
        <el-tag :type="dictType(ORDER_STATUS, o.status)" size="small" effect="plain">
          {{ dictLabel(ORDER_STATUS, o.status) }}
        </el-tag>
      </span>
    </el-option>
  </el-select>
</template>

<style scoped>
.wo-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.wo-no {
  font-size: 12.5px;
  flex-shrink: 0;
}

.wo-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #5b6572;
  font-size: 12.5px;
}
</style>
