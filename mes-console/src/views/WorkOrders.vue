<script setup>
/**
 * 工单管理 —— 建单、派工、报工、关闭，以及查看报工明细。
 *
 * 一个刻意的设计：操作按钮按工单当前状态**动态显示**，而不是全摆出来让用户点了再被拒。
 * 后端会拦截非法流转（这是必须的），但界面上不该诱导用户去做必然失败的操作。
 * 界面这一层负责"让人做对的事"，后端负责"兜住做错的事"。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import api from '../api'
import {
  ORDER_STATUS,
  ORDER_STATUS_OPTIONS,
  dictType,
  dictLabel,
  num,
  rateClass
} from '../utils/dict'

// ---------------------------------------------------------------- 列表
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ pageNum: 1, pageSize: 10, status: '', keyword: '' })

async function load() {
  loading.value = true
  try {
    const data = await api.workOrder.page(query)
    rows.value = data.records || []
    total.value = data.total || 0
  } catch (err) {
    ElMessage.error(`加载工单失败：${err.message}`)
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

// ---------------------------------------------------------------- 状态判断
// 与后端状态机保持一致：派工允许 NEW/DISPATCHED，报工只允许 DISPATCHED/IN_PROGRESS，
// 关闭允许 DISPATCHED/IN_PROGRESS
const canDispatch = (row) => ['NEW', 'DISPATCHED'].includes(row.status)
const canReport = (row) => ['DISPATCHED', 'IN_PROGRESS'].includes(row.status)
const canClose = (row) => ['DISPATCHED', 'IN_PROGRESS'].includes(row.status)

// ---------------------------------------------------------------- 建单
const createVisible = ref(false)
const createForm = reactive({
  productCode: '',
  productName: '',
  planQty: 100,
  lineCode: '',
  workshop: '',
  remark: ''
})
const submitting = ref(false)

function openCreate() {
  Object.assign(createForm, {
    productCode: '',
    productName: '',
    planQty: 100,
    lineCode: '',
    workshop: '',
    remark: ''
  })
  createVisible.value = true
}

async function submitCreate() {
  if (!createForm.productCode.trim() || !createForm.productName.trim()) {
    ElMessage.warning('产品编码与产品名称为必填项')
    return
  }
  if (!createForm.planQty || createForm.planQty < 1) {
    ElMessage.warning('计划数量必须大于 0')
    return
  }
  submitting.value = true
  try {
    const order = await api.workOrder.create({ ...createForm })
    ElMessage.success(`工单已创建：${order.orderNo}`)
    createVisible.value = false
    search()
  } catch (err) {
    ElMessage.error(`创建失败：${err.message}（${err.detail}）`)
  } finally {
    submitting.value = false
  }
}

// ---------------------------------------------------------------- 派工 / 报工 / 关闭
const dispatchVisible = ref(false)
const dispatchTarget = ref(null)
const dispatchForm = reactive({ lineCode: '', workshop: '', remark: '' })

function openDispatch(row) {
  dispatchTarget.value = row
  Object.assign(dispatchForm, {
    lineCode: row.lineCode || '',
    workshop: row.workshop || '',
    remark: ''
  })
  dispatchVisible.value = true
}

async function submitDispatch() {
  if (!dispatchForm.lineCode.trim()) {
    ElMessage.warning('产线编号为必填项')
    return
  }
  submitting.value = true
  try {
    await api.workOrder.dispatch(dispatchTarget.value.orderNo, { ...dispatchForm })
    ElMessage.success('派工成功')
    dispatchVisible.value = false
    load()
  } catch (err) {
    ElMessage.error(`派工失败：${err.message}（${err.detail}）`)
  } finally {
    submitting.value = false
  }
}

const reportVisible = ref(false)
const reportTarget = ref(null)
const reportForm = reactive({ reportQty: 10, qualifiedQty: null, defectiveQty: null, worker: '', equipmentCode: '', remark: '' })

// 报工时的实时提示：合格+不良必须等于报工数，这里先算给用户看，避免提交后才被拒
const reportCheck = computed(() => {
  const q = Number(reportForm.reportQty || 0)
  const ql = reportForm.qualifiedQty === null || reportForm.qualifiedQty === '' ? null : Number(reportForm.qualifiedQty)
  const df = reportForm.defectiveQty === null || reportForm.defectiveQty === '' ? null : Number(reportForm.defectiveQty)

  if (ql === null && df === null) {
    return { ok: true, text: `未填合格/不良，将按「全部合格 ${q} 件」处理` }
  }
  if (ql === null) return { ok: true, text: `合格数将自动推算为 ${q - df} 件` }
  if (df === null) return { ok: true, text: `不良数将自动推算为 ${q - ql} 件` }
  if (ql + df !== q) return { ok: false, text: `合格 ${ql} + 不良 ${df} = ${ql + df}，与报工数 ${q} 不符，会被拒绝` }
  return { ok: true, text: `合格 ${ql} + 不良 ${df} = ${q}，校验通过` }
})

function openReport(row) {
  reportTarget.value = row
  Object.assign(reportForm, {
    reportQty: 10,
    qualifiedQty: null,
    defectiveQty: null,
    worker: '',
    equipmentCode: '',
    remark: ''
  })
  reportVisible.value = true
}

async function submitReport() {
  if (!reportForm.worker.trim()) {
    ElMessage.warning('报工人为必填项')
    return
  }
  if (!reportCheck.value.ok) {
    ElMessage.warning(reportCheck.value.text)
    return
  }
  submitting.value = true
  try {
    const updated = await api.workOrder.report(reportTarget.value.orderNo, { ...reportForm })
    ElMessage.success(
      `报工成功，累计 ${updated.finishedQty}／计划 ${updated.planQty}（进度 ${updated.progressRate}%）`
    )
    reportVisible.value = false
    load()
  } catch (err) {
    ElMessage.error(`报工失败：${err.message}（${err.detail}）`)
  } finally {
    submitting.value = false
  }
}

async function closeOrder(row) {
  try {
    await ElMessageBox.confirm(
      `确认关闭工单 ${row.orderNo}？关闭后不可再报工，且不能撤销。`,
      '关闭工单',
      { type: 'warning', confirmButtonText: '确认关闭', cancelButtonText: '取消' }
    )
  } catch {
    return // 用户取消
  }
  try {
    await api.workOrder.close(row.orderNo, {})
    ElMessage.success('工单已关闭')
    load()
  } catch (err) {
    ElMessage.error(`关闭失败：${err.message}（${err.detail}）`)
  }
}

// ---------------------------------------------------------------- 详情抽屉
const detailVisible = ref(false)
const detail = ref(null)
const detailLoading = ref(false)

async function openDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await api.workOrder.detail(row.orderNo)
  } catch (err) {
    ElMessage.error(`加载详情失败：${err.message}`)
  } finally {
    detailLoading.value = false
  }
}
</script>

<template>
  <div class="page">
    <!-- 筛选 -->
    <div class="toolbar">
      <el-input
        v-model="query.keyword"
        placeholder="搜工单号或产品名称"
        clearable
        style="width: 220px"
        @keyup.enter="search"
      />
      <el-select v-model="query.status" placeholder="全部状态" clearable style="width: 140px" @change="search">
        <el-option v-for="o in ORDER_STATUS_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-button type="primary" :icon="'Search'" @click="search">查询</el-button>
      <el-button :icon="'RefreshLeft'" @click="resetQuery">重置</el-button>
      <div class="spacer"></div>
      <el-button type="primary" :icon="'Plus'" @click="openCreate">新建工单</el-button>
    </div>

    <!-- 列表 -->
    <el-card shadow="never">
      <el-table v-loading="loading" :data="rows" size="default" empty-text="暂无工单">
        <el-table-column prop="orderNo" label="工单号" width="185">
          <template #default="{ row }">
            <span class="mono clickable-code" @click="openDetail(row)">{{ row.orderNo }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="productName" label="产品" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.productName }}</div>
            <div class="mono text-muted" style="font-size: 11.5px">{{ row.productCode }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="dictType(ORDER_STATUS, row.status)" size="small">
              {{ dictLabel(ORDER_STATUS, row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="150">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.min(100, Number(row.progressRate) || 0)"
              :stroke-width="10"
              :show-text="false"
            />
            <div class="progress-text">
              <span class="mono">{{ row.finishedQty }}／{{ row.planQty }}</span>
              <span class="text-muted">{{ num(row.progressRate, 1) }}%</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="良率" width="86">
          <template #default="{ row }">
            <span :class="rateClass(row.yieldRate)">{{ row.finishedQty ? `${num(row.yieldRate, 1)}%` : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="lineCode" label="产线" width="100">
          <template #default="{ row }">
            <span class="mono">{{ row.lineCode || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="workshop" label="车间" width="110" show-overflow-tooltip />
        <el-table-column prop="createTime" label="创建时间" width="160">
          <template #default="{ row }"><span class="mono">{{ row.createTime }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canDispatch(row)" link type="primary" size="small" @click="openDispatch(row)">
              派工
            </el-button>
            <el-button v-if="canReport(row)" link type="primary" size="small" @click="openReport(row)">
              报工
            </el-button>
            <el-button v-if="canClose(row)" link type="warning" size="small" @click="closeOrder(row)">
              关闭
            </el-button>
            <el-button link size="small" @click="openDetail(row)">详情</el-button>
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

    <!-- 新建工单 -->
    <el-dialog v-model="createVisible" title="新建工单" width="520px">
      <el-form :model="createForm" label-width="94px">
        <el-form-item label="产品编码" required>
          <el-input v-model="createForm.productCode" placeholder="如 P-FLANGE-100" maxlength="32" />
        </el-form-item>
        <el-form-item label="产品名称" required>
          <el-input v-model="createForm.productName" placeholder="如 法兰盘" maxlength="64" />
        </el-form-item>
        <el-form-item label="计划数量" required>
          <el-input-number v-model="createForm.planQty" :min="1" :max="1000000" style="width: 180px" />
          <span class="text-muted" style="margin-left: 10px; font-size: 12px">上限 1000000</span>
        </el-form-item>
        <el-form-item label="产线编号">
          <el-input v-model="createForm.lineCode" placeholder="可留空，派工时再指定" maxlength="32" />
        </el-form-item>
        <el-form-item label="车间">
          <el-input v-model="createForm.workshop" placeholder="选填" maxlength="64" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.remark" type="textarea" :rows="2" maxlength="255" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 派工 -->
    <el-dialog v-model="dispatchVisible" title="工单派工" width="460px">
      <el-alert type="info" :closable="false" style="margin-bottom: 14px">
        <template #default>
          <span class="mono">{{ dispatchTarget?.orderNo }}</span>
          &nbsp;派工后状态流转为「已派工」，可以开始报工。
        </template>
      </el-alert>
      <el-form :model="dispatchForm" label-width="84px">
        <el-form-item label="产线编号" required>
          <el-input v-model="dispatchForm.lineCode" placeholder="如 L-A1" maxlength="32" />
        </el-form-item>
        <el-form-item label="车间">
          <el-input v-model="dispatchForm.workshop" placeholder="选填" maxlength="64" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="dispatchForm.remark" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dispatchVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitDispatch">确认派工</el-button>
      </template>
    </el-dialog>

    <!-- 报工 -->
    <el-dialog v-model="reportVisible" title="工单报工" width="520px">
      <el-alert type="info" :closable="false" style="margin-bottom: 14px">
        <template #default>
          <span class="mono">{{ reportTarget?.orderNo }}</span>
          &nbsp;已报 <b>{{ reportTarget?.finishedQty }}</b>／计划 <b>{{ reportTarget?.planQty }}</b>
          &nbsp;· 超报会被后端拦截
        </template>
      </el-alert>
      <el-form :model="reportForm" label-width="94px">
        <el-form-item label="报工数量" required>
          <el-input-number v-model="reportForm.reportQty" :min="1" :max="1000000" style="width: 180px" />
        </el-form-item>
        <el-form-item label="合格数量">
          <el-input-number v-model="reportForm.qualifiedQty" :min="0" :max="1000000" style="width: 180px" placeholder="留空自动推算" />
        </el-form-item>
        <el-form-item label="不良数量">
          <el-input-number v-model="reportForm.defectiveQty" :min="0" :max="1000000" style="width: 180px" placeholder="留空自动推算" />
        </el-form-item>
        <el-form-item>
          <el-alert :type="reportCheck.ok ? 'success' : 'error'" :closable="false" style="width: 100%">
            {{ reportCheck.text }}
          </el-alert>
        </el-form-item>
        <el-form-item label="报工人" required>
          <el-input v-model="reportForm.worker" placeholder="如 张三" maxlength="32" />
        </el-form-item>
        <el-form-item label="设备编号">
          <el-input v-model="reportForm.equipmentCode" placeholder="选填" maxlength="32" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="reportForm.remark" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reportVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitReport">确认报工</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="工单详情" size="620px">
      <div v-loading="detailLoading">
        <template v-if="detail">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="工单号" :span="2">
              <span class="mono">{{ detail.orderNo }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="产品">{{ detail.productName }}</el-descriptions-item>
            <el-descriptions-item label="产品编码"><span class="mono">{{ detail.productCode }}</span></el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="dictType(ORDER_STATUS, detail.status)" size="small">
                {{ dictLabel(ORDER_STATUS, detail.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="产线"><span class="mono">{{ detail.lineCode || '—' }}</span></el-descriptions-item>
            <el-descriptions-item label="计划／报工">
              <span class="mono">{{ detail.finishedQty }}／{{ detail.planQty }}</span>
              （{{ num(detail.progressRate, 1) }}%）
            </el-descriptions-item>
            <el-descriptions-item label="合格／不良">
              <span class="mono">{{ detail.qualifiedQty }}／{{ detail.defectiveQty }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="实际开工">{{ detail.actualStartTime || '—' }}</el-descriptions-item>
            <el-descriptions-item label="实际完工">{{ detail.actualEndTime || '—' }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ detail.remark || '—' }}</el-descriptions-item>
          </el-descriptions>

          <div class="section-title" style="margin-top: 20px">
            报工明细
            <span class="section-hint">共 {{ (detail.reports || []).length }} 笔</span>
          </div>
          <el-table :data="detail.reports || []" size="small" empty-text="还没有报工记录">
            <el-table-column prop="reportNo" label="报工单号" width="180">
              <template #default="{ row }"><span class="mono">{{ row.reportNo }}</span></template>
            </el-table-column>
            <el-table-column label="报工数" width="80">
              <template #default="{ row }"><span class="mono">{{ row.reportQty }}</span></template>
            </el-table-column>
            <el-table-column label="合格" width="70">
              <template #default="{ row }"><span class="mono">{{ row.qualifiedQty }}</span></template>
            </el-table-column>
            <el-table-column label="不良" width="70">
              <template #default="{ row }">
                <span class="mono" :class="row.defectiveQty ? 'is-bad' : ''">{{ row.defectiveQty }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="worker" label="报工人" width="90" />
            <el-table-column prop="reportTime" label="报工时间" min-width="160">
              <template #default="{ row }"><span class="mono">{{ row.reportTime }}</span></template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.progress-text {
  display: flex;
  justify-content: space-between;
  font-size: 11.5px;
  margin-top: 2px;
}

.is-bad {
  color: #cf222e;
}

.is-warn {
  color: #9a6700;
}

.is-good {
  color: #1a7f37;
}
</style>
