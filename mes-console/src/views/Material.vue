<script setup>
/**
 * 物料批次 —— 建档、绑定工单、出货消耗。
 *
 * 核心约束在界面上体现为「按状态决定可用操作」：已消耗的批次不能再绑定或出货，
 * 已绑定他单的批次不能再改绑。后端是最终防线，界面负责不诱导用户做无效操作。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import api from '../api'
import { BATCH_STATUS, BATCH_STATUS_OPTIONS, dictLabel, dictType } from '../utils/dict'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ pageNum: 1, pageSize: 10, status: '', keyword: '' })

async function load() {
  loading.value = true
  try {
    const data = await api.material.page(query)
    rows.value = data.records || []
    total.value = data.total || 0
  } catch (err) {
    ElMessage.error(`加载批次失败：${err.message}`)
  } finally {
    loading.value = false
  }
}

function search() {
  query.pageNum = 1
  load()
}

function resetQuery() {
  query.status = ''
  query.keyword = ''
  search()
}

onMounted(load)

// 状态 → 可用操作（与后端规则一致）
const canBind = (row) => row.status === 'IN_STOCK'
const canOutbound = (row) => ['IN_USE', 'IN_STOCK'].includes(row.status)

// ---------------------------------------------------------------- 建档
const createVisible = ref(false)
const submitting = ref(false)
const form = reactive({
  batchNo: '',
  materialCode: '',
  materialName: '',
  orderNo: '',
  supplier: '',
  qty: 100,
  unit: '件',
  remark: ''
})

function openCreate() {
  Object.assign(form, {
    batchNo: '',
    materialCode: '',
    materialName: '',
    orderNo: '',
    supplier: '',
    qty: 100,
    unit: '件',
    remark: ''
  })
  createVisible.value = true
}

async function submitCreate() {
  if (!form.materialCode.trim() || !form.materialName.trim()) {
    ElMessage.warning('物料编码与名称为必填项')
    return
  }
  if (!form.qty || form.qty < 1) {
    ElMessage.warning('数量必须大于 0')
    return
  }
  submitting.value = true
  try {
    const batch = await api.material.create({ ...form })
    ElMessage.success(
      `批次已建档：${batch.batchNo}（${dictLabel(BATCH_STATUS, batch.status)}）`
    )
    createVisible.value = false
    search()
  } catch (err) {
    ElMessage.error(`建档失败：${err.message}（${err.detail}）`)
  } finally {
    submitting.value = false
  }
}

// ---------------------------------------------------------------- 绑定
const bindVisible = ref(false)
const bindTarget = ref(null)
const bindOrderNo = ref('')

function openBind(row) {
  bindTarget.value = row
  bindOrderNo.value = ''
  bindVisible.value = true
}

async function submitBind() {
  if (!bindOrderNo.value.trim()) {
    ElMessage.warning('请填写要绑定的工单号')
    return
  }
  submitting.value = true
  try {
    await api.material.bind(bindTarget.value.batchNo, bindOrderNo.value.trim())
    ElMessage.success('绑定成功，批次状态已转为「在用」')
    bindVisible.value = false
    load()
  } catch (err) {
    ElMessage.error(`绑定失败：${err.message}（${err.detail}）`)
  } finally {
    submitting.value = false
  }
}

// ---------------------------------------------------------------- 出货
async function outbound(row) {
  try {
    await ElMessageBox.confirm(
      `确认将批次 ${row.batchNo} 出货消耗？出货后状态转为「已消耗」，不可再绑定工单。`,
      '批次出货',
      { type: 'warning', confirmButtonText: '确认出货', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await api.material.outbound(row.batchNo, '')
    ElMessage.success('已出货消耗，并落下一条 OUTBOUND 追溯节点')
    load()
  } catch (err) {
    ElMessage.error(`出货失败：${err.message}（${err.detail}）`)
  }
}
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-input
        v-model="query.keyword"
        placeholder="搜批次号或物料名称"
        clearable
        style="width: 220px"
        @keyup.enter="search"
      />
      <el-select v-model="query.status" placeholder="全部状态" clearable style="width: 140px" @change="search">
        <el-option v-for="o in BATCH_STATUS_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-button type="primary" :icon="'Search'" @click="search">查询</el-button>
      <el-button :icon="'RefreshLeft'" @click="resetQuery">重置</el-button>
      <div class="spacer"></div>
      <el-button type="primary" :icon="'Plus'" @click="openCreate">批次建档</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="rows" size="default" empty-text="暂无批次记录">
        <el-table-column prop="batchNo" label="批次号" width="185">
          <template #default="{ row }"><span class="mono">{{ row.batchNo }}</span></template>
        </el-table-column>
        <el-table-column prop="materialName" label="物料" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.materialName }}</div>
            <div class="mono text-muted" style="font-size: 11.5px">{{ row.materialCode }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="96">
          <template #default="{ row }">
            <el-tag :type="dictType(BATCH_STATUS, row.status)" size="small">
              {{ dictLabel(BATCH_STATUS, row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="100">
          <template #default="{ row }">
            <span class="mono">{{ row.qty }}</span>
            <span class="text-muted">{{ row.unit || '' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="orderNo" label="绑定工单" width="180">
          <template #default="{ row }">
            <span v-if="row.orderNo" class="mono">{{ row.orderNo }}</span>
            <span v-else class="text-muted">未绑定</span>
          </template>
        </el-table-column>
        <el-table-column prop="supplier" label="供应商" width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.supplier || '—' }}</template>
        </el-table-column>
        <el-table-column prop="inboundTime" label="入库时间" width="160">
          <template #default="{ row }"><span class="mono">{{ row.inboundTime }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canBind(row)" link type="primary" size="small" @click="openBind(row)">
              绑定工单
            </el-button>
            <el-button v-if="canOutbound(row)" link type="warning" size="small" @click="outbound(row)">
              出货
            </el-button>
            <span v-if="!canBind(row) && !canOutbound(row)" class="text-muted" style="font-size: 12px">
              已终结
            </span>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="query.pageNum"
        v-model:page-size="query.pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 14px; justify-content: flex-end"
        @current-change="load"
        @size-change="search"
      />
    </el-card>

    <!-- 建档 -->
    <el-dialog v-model="createVisible" title="物料批次建档" width="520px">
      <el-alert type="info" :closable="false" style="margin-bottom: 14px">
        <template #default>
          建档时可直接绑定工单（状态即为「在用」）；不绑工单则落在「在库」。
          一个批次只能绑一个工单，改绑会被拒绝 —— 这是追溯不串线的保证。
        </template>
      </el-alert>
      <el-form :model="form" label-width="94px">
        <el-form-item label="批次号">
          <el-input v-model="form.batchNo" placeholder="留空由系统生成" maxlength="32" />
        </el-form-item>
        <el-form-item label="物料编码" required>
          <el-input v-model="form.materialCode" placeholder="如 M-STEEL-01" maxlength="32" />
        </el-form-item>
        <el-form-item label="物料名称" required>
          <el-input v-model="form.materialName" placeholder="如 45# 圆钢" maxlength="64" />
        </el-form-item>
        <el-form-item label="绑定工单">
          <el-input v-model="form.orderNo" placeholder="选填，如 WO20261012..." maxlength="32" />
        </el-form-item>
        <el-form-item label="供应商">
          <el-input v-model="form.supplier" placeholder="选填" maxlength="64" />
        </el-form-item>
        <el-form-item label="数量" required>
          <el-input-number v-model="form.qty" :min="1" style="width: 160px" />
          <el-input v-model="form.unit" placeholder="单位" style="width: 90px; margin-left: 10px" maxlength="16" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">建档</el-button>
      </template>
    </el-dialog>

    <!-- 绑定工单 -->
    <el-dialog v-model="bindVisible" title="绑定工单" width="440px">
      <el-alert type="info" :closable="false" style="margin-bottom: 14px">
        <template #default>
          批次 <span class="mono">{{ bindTarget?.batchNo }}</span>
          （{{ bindTarget?.materialName }}）
        </template>
      </el-alert>
      <el-form label-width="80px">
        <el-form-item label="工单号" required>
          <el-input v-model="bindOrderNo" placeholder="如 WO20261012..." maxlength="32" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="bindVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitBind">确认绑定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
