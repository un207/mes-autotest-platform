<script setup>
/**
 * 质量管理 —— 质检录入、不良分布、按工单查不良明细。
 *
 * 界面上刻意把「结论由数量推导」这条规则显性化：填完数量就实时告诉用户
 * 系统会判成什么，并说明为什么人工填的结论若与数量矛盾会被拒绝。
 * 规则不该只藏在后端报错里，用户提前知道才叫好设计。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import api from '../api'
import EChart from '../components/EChart.vue'
import WorkOrderSelect from '../components/WorkOrderSelect.vue'
import { INSPECT_RESULT, INSPECT_TYPE, INSPECT_TYPE_OPTIONS, dictLabel, dictType } from '../utils/dict'

// ---------------------------------------------------------------- 列表
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ pageNum: 1, pageSize: 10, orderNo: '', result: '', inspectType: '' })

async function load() {
  loading.value = true
  try {
    const data = await api.quality.page(query)
    rows.value = data.records || []
    total.value = data.total || 0
  } catch (err) {
    ElMessage.error(`加载质检记录失败：${err.message}`)
  } finally {
    loading.value = false
  }
}

function search() {
  query.pageNum = 1
  load()
}

function resetQuery() {
  query.orderNo = ''
  query.result = ''
  query.inspectType = ''
  search()
}

// ---------------------------------------------------------------- 不良分布
const defectRows = ref([])

async function loadDefectSummary() {
  try {
    defectRows.value = await api.quality.defectSummary()
  } catch (err) {
    ElMessage.error(`加载不良分布失败：${err.message}`)
  }
}

onMounted(() => {
  load()
  loadDefectSummary()
})

const defectPieOption = computed(() => {
  const rows = defectRows.value.filter((r) => r.defectiveQty > 0)
  return {
    tooltip: { trigger: 'item', formatter: '{b}<br/>不良数 {c}（{d}%）' },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 0,
      top: 'center',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { fontSize: 11, color: '#5b6572' }
    },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['36%', '50%'],
        avoidLabelOverlap: true,
        label: { show: false },
        data: rows.map((r) => ({ name: r.defectCode || '(未填代码)', value: r.defectiveQty }))
      }
    ]
  }
})

// ---------------------------------------------------------------- 录入
const createVisible = ref(false)
const submitting = ref(false)
const form = reactive({
  orderNo: '',
  batchNo: '',
  inspectType: 'IPQC',
  inspectQty: 20,
  qualifiedQty: null,
  defectiveQty: null,
  defectCode: '',
  inspector: '',
  remark: ''
})

// 实时推导结论 —— 与后端 InspectResult.derive 的口径一致
const derived = computed(() => {
  const total = Number(form.inspectQty || 0)
  const ql =
    form.qualifiedQty === null || form.qualifiedQty === '' ? null : Number(form.qualifiedQty)
  const df =
    form.defectiveQty === null || form.defectiveQty === '' ? null : Number(form.defectiveQty)

  let q = ql
  let d = df
  if (q === null && d === null) {
    q = total
    d = 0
  } else if (q === null) {
    q = total - d
  } else if (d === null) {
    d = total - q
  }

  const negative = q < 0 || d < 0
  const mismatch = !negative && q + d !== total
  const needCode = d > 0 && !form.defectCode.trim()

  return {
    qualified: q,
    defective: d,
    result: d > 0 ? 'FAIL' : 'PASS',
    negative,
    mismatch,
    needCode,
    ok: !negative && !mismatch && !needCode
  }
})

function openCreate() {
  Object.assign(form, {
    orderNo: '',
    batchNo: '',
    inspectType: 'IPQC',
    inspectQty: 20,
    qualifiedQty: null,
    defectiveQty: null,
    defectCode: '',
    inspector: '',
    remark: ''
  })
  createVisible.value = true
}

async function submitCreate() {
  if (!form.orderNo.trim()) {
    ElMessage.warning('工单号为必填项')
    return
  }
  if (!form.inspector.trim()) {
    ElMessage.warning('质检员为必填项')
    return
  }
  if (!derived.value.ok) {
    ElMessage.warning('数量或不良代码不符合规则，请按提示修正')
    return
  }
  submitting.value = true
  try {
    const res = await api.quality.create({ ...form })
    ElMessage.success(`质检已录入，系统判定：${dictLabel(INSPECT_RESULT, res.result)}`)
    createVisible.value = false
    search()
    loadDefectSummary()
  } catch (err) {
    ElMessage.error(`录入失败：${err.message}（${err.detail}）`)
  } finally {
    submitting.value = false
  }
}

// ---------------------------------------------------------------- 不良明细抽屉
const defectsVisible = ref(false)
const defectsLoading = ref(false)
const defects = ref([])
const defectsOrderNo = ref('')

async function openDefects(row) {
  defectsOrderNo.value = row.orderNo
  defectsVisible.value = true
  defectsLoading.value = true
  defects.value = []
  try {
    defects.value = await api.quality.defectsByOrder(row.orderNo)
  } catch (err) {
    ElMessage.error(`加载不良明细失败：${err.message}`)
  } finally {
    defectsLoading.value = false
  }
}
</script>

<template>
  <div class="page">
    <el-row :gutter="16">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never">
          <div class="toolbar" style="margin-bottom: 12px">
            <WorkOrderSelect
              v-model="query.orderNo"
              placeholder="按工单筛选"
              clearable
              width="220px"
              @change="search"
            />
            <el-select v-model="query.inspectType" placeholder="全部检验类型" clearable style="width: 150px" @change="search">
              <el-option v-for="o in INSPECT_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-select v-model="query.result" placeholder="全部结论" clearable style="width: 120px" @change="search">
              <el-option label="合格" value="PASS" />
              <el-option label="不合格" value="FAIL" />
            </el-select>
            <el-button type="primary" :icon="'Search'" @click="search">查询</el-button>
            <el-button :icon="'RefreshLeft'" @click="resetQuery">重置</el-button>
            <div class="spacer"></div>
            <el-button type="primary" :icon="'Plus'" @click="openCreate">录入质检</el-button>
          </div>

          <el-table v-loading="loading" :data="rows" size="default" empty-text="暂无质检记录">
            <el-table-column prop="inspectNo" label="质检单号" width="175">
              <template #default="{ row }"><span class="mono">{{ row.inspectNo }}</span></template>
            </el-table-column>
            <el-table-column prop="orderNo" label="工单号" width="175">
              <template #default="{ row }">
                <span class="mono clickable-code" @click="openDefects(row)">{{ row.orderNo }}</span>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="96">
              <template #default="{ row }">{{ dictLabel(INSPECT_TYPE, row.inspectType) }}</template>
            </el-table-column>
            <el-table-column label="结论" width="90">
              <template #default="{ row }">
                <el-tag :type="dictType(INSPECT_RESULT, row.result)" size="small">
                  {{ dictLabel(INSPECT_RESULT, row.result) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="检验／合格／不良" width="150">
              <template #default="{ row }">
                <span class="mono">{{ row.inspectQty }}／{{ row.qualifiedQty }}／</span>
                <span class="mono" :class="row.defectiveQty ? 'is-bad' : ''">{{ row.defectiveQty }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="defectCode" label="不良代码" min-width="140" show-overflow-tooltip>
              <template #default="{ row }"><span class="mono">{{ row.defectCode || '—' }}</span></template>
            </el-table-column>
            <el-table-column prop="inspector" label="质检员" width="100" />
            <el-table-column prop="inspectTime" label="检验时间" width="160">
              <template #default="{ row }"><span class="mono">{{ row.inspectTime }}</span></template>
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
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never">
          <div class="section-title">
            不良代码分布
            <span class="section-hint">按数量占比</span>
          </div>
          <EChart v-if="defectRows.filter((r) => r.defectiveQty > 0).length" :option="defectPieOption" height="260px" />
          <el-empty v-else description="暂无不良记录" :image-size="70" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 录入质检 -->
    <el-dialog v-model="createVisible" title="录入质检记录" width="560px">
      <el-alert type="info" :closable="false" style="margin-bottom: 14px">
        <template #default>
          结论由系统按数量推导：<b>不良数 &gt; 0 判为不合格</b>，不接受人工指定相反结论。
        </template>
      </el-alert>
      <el-form :model="form" label-width="94px">
        <el-form-item label="工单号" required>
          <WorkOrderSelect v-model="form.orderNo" width="100%" />
        </el-form-item>
        <el-form-item label="批次号">
          <el-input v-model="form.batchNo" placeholder="选填；填了会校验批次是否属于该工单" maxlength="32" />
        </el-form-item>
        <el-form-item label="检验类型" required>
          <el-select v-model="form.inspectType" style="width: 180px">
            <el-option v-for="o in INSPECT_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="检验数量" required>
          <el-input-number v-model="form.inspectQty" :min="1" :max="1000000" style="width: 180px" />
        </el-form-item>
        <el-form-item label="合格数量">
          <el-input-number v-model="form.qualifiedQty" :min="0" :max="1000000" style="width: 180px" placeholder="留空自动推算" />
        </el-form-item>
        <el-form-item label="不良数量">
          <el-input-number v-model="form.defectiveQty" :min="0" :max="1000000" style="width: 180px" placeholder="留空自动推算" />
        </el-form-item>

        <!-- 实时校验提示 -->
        <el-form-item>
          <el-alert :type="derived.ok ? 'success' : 'error'" :closable="false" style="width: 100%">
            <template #default>
              <div>
                合格 <b>{{ derived.qualified }}</b> ＋ 不良 <b>{{ derived.defective }}</b>
                ＝ <b>{{ derived.qualified + derived.defective }}</b>（检验 {{ form.inspectQty }}）
                ── 系统判定：<b>{{ dictLabel(INSPECT_RESULT, derived.result) }}</b>
              </div>
              <div v-if="derived.negative" style="margin-top: 4px">合格数与不良数都不能为负</div>
              <div v-else-if="derived.mismatch" style="margin-top: 4px">合格＋不良必须等于检验数量，否则会被拒绝</div>
              <div v-else-if="derived.needCode" style="margin-top: 4px">存在不良品，必须填写不良代码（否则追溯链会在不良环节断掉）</div>
            </template>
          </el-alert>
        </el-form-item>

        <el-form-item label="不良代码" :required="derived.defective > 0">
          <el-input v-model="form.defectCode" placeholder="如 D-DIM-01 尺寸超差" maxlength="32" />
        </el-form-item>
        <el-form-item label="质检员" required>
          <el-input v-model="form.inspector" placeholder="如 李四" maxlength="32" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">录入</el-button>
      </template>
    </el-dialog>

    <!-- 不良明细 -->
    <el-drawer v-model="defectsVisible" title="不良明细" size="560px">
      <div class="section-hint" style="margin-bottom: 12px">
        工单 <span class="mono">{{ defectsOrderNo }}</span> 的全部不合格记录
      </div>
      <el-table v-loading="defectsLoading" :data="defects" size="small" empty-text="该工单没有不良记录">
        <el-table-column prop="inspectNo" label="质检单号" width="170">
          <template #default="{ row }"><span class="mono">{{ row.inspectNo }}</span></template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">{{ dictLabel(INSPECT_TYPE, row.inspectType) }}</template>
        </el-table-column>
        <el-table-column prop="defectCode" label="不良代码" width="140">
          <template #default="{ row }"><span class="mono">{{ row.defectCode }}</span></template>
        </el-table-column>
        <el-table-column label="不良数" width="76">
          <template #default="{ row }"><span class="mono is-bad">{{ row.defectiveQty }}</span></template>
        </el-table-column>
        <el-table-column prop="inspector" label="质检员" width="90" />
        <el-table-column prop="inspectTime" label="时间" min-width="150">
          <template #default="{ row }"><span class="mono">{{ row.inspectTime }}</span></template>
        </el-table-column>
      </el-table>
    </el-drawer>
  </div>
</template>

<style scoped>
.is-bad {
  color: #cf222e;
}
</style>
