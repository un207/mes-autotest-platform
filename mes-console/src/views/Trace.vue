<script setup>
/**
 * 追溯查询 —— 正反两个方向查同一批数据。
 *
 *   正向（按批次）：这批原料最后流到了哪个工单、中间经过了哪些环节
 *   反向（按工单）：这张工单用了哪些原料、出过什么不良、完整节点流水
 *
 * 用时间线而不是表格呈现节点流水：追溯本身就是"按时间发生的链条"，
 * 时间线能直接把先后顺序和完整性表达出来，表格只能让人自己去对时间。
 */
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

import api from '../api'
import { BATCH_STATUS, INSPECT_RESULT, TRACE_NODE, dictLabel, dictType } from '../utils/dict'

const mode = ref('order') // order = 反向追溯 / batch = 正向追溯
const keyword = ref('')
const loading = ref(false)
const result = ref(null)
const searched = ref(false)

async function search() {
  const kw = keyword.value.trim()
  if (!kw) {
    ElMessage.warning(mode.value === 'order' ? '请输入工单号' : '请输入批次号')
    return
  }
  loading.value = true
  searched.value = true
  result.value = null
  try {
    result.value =
      mode.value === 'order' ? await api.trace.byOrder(kw) : await api.trace.byBatch(kw)
  } catch (err) {
    ElMessage.error(`追溯失败：${err.message}（${err.detail}）`)
  } finally {
    loading.value = false
  }
}

function switchMode(m) {
  mode.value = m
  keyword.value = ''
  result.value = null
  searched.value = false
}

/** 节点流水的类型（用于时间线着色） */
function nodeType(node) {
  return dictType(TRACE_NODE, node.nodeType)
}

const nodeLabel = (node) => dictLabel(TRACE_NODE, node.nodeType)

/** 反向追溯拿到的工单基本信息 */
const orderInfo = computed(() => (result.value?.order ? result.value.order : null))
/** 正向追溯拿到的批次基本信息 */
const batchInfo = computed(() => (result.value?.batch ? result.value.batch : null))

/** 统一取节点列表：两个方向的字段名不同，在这里归一 */
const nodes = computed(() => result.value?.nodes || [])

/** 统一取批次列表 */
const batches = computed(() => {
  if (!result.value) return []
  if (Array.isArray(result.value.batches)) return result.value.batches
  if (batchInfo.value) return [batchInfo.value]
  return []
})

const defects = computed(() => result.value?.defects || [])
</script>

<template>
  <div class="page">
    <el-card shadow="never" style="margin-bottom: 16px">
      <div class="section-title">
        追溯查询
        <span class="section-hint">
          正向查「这批料去了哪」，反向查「这张工单用了什么料、出过什么问题」
        </span>
      </div>

      <el-radio-group :model-value="mode" style="margin-bottom: 14px" @change="switchMode">
        <el-radio-button value="order">反向追溯（按工单）</el-radio-button>
        <el-radio-button value="batch">正向追溯（按批次）</el-radio-button>
      </el-radio-group>

      <div class="toolbar" style="margin-bottom: 0">
        <el-input
          v-model="keyword"
          :placeholder="mode === 'order' ? '输入工单号，如 WO20261012...' : '输入批次号，如 B-...'"
          clearable
          style="width: 320px"
          @keyup.enter="search"
        />
        <el-button type="primary" :icon="'Search'" :loading="loading" @click="search">追溯</el-button>
        <span class="section-hint">
          追溯数据来自「只增不改」的流水表 —— 节点一旦落下就不会被改写，结论才可信。
        </span>
      </div>
    </el-card>

    <div v-loading="loading">
      <!-- 未查过 -->
      <el-empty v-if="!searched" description="输入单号开始追溯" />

      <!-- 查了但没结果 -->
      <el-empty
        v-else-if="!result"
        :description="mode === 'order' ? '未找到该工单的追溯信息' : '未找到该批次的追溯信息'"
      />

      <template v-else>
        <el-row :gutter="16">
          <!-- 左侧：主体信息 + 节点流水 -->
          <el-col :xs="24" :lg="15">
            <!-- 反向追溯：工单信息 -->
            <el-card v-if="orderInfo" shadow="never" style="margin-bottom: 16px">
              <div class="section-title">工单信息</div>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="工单号" :span="2">
                  <span class="mono">{{ orderInfo.orderNo }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="产品">{{ orderInfo.productName }}</el-descriptions-item>
                <el-descriptions-item label="状态">{{ orderInfo.statusLabel || orderInfo.status }}</el-descriptions-item>
                <el-descriptions-item label="计划／报工">
                  <span class="mono">{{ orderInfo.finishedQty }}／{{ orderInfo.planQty }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="合格／不良">
                  <span class="mono">{{ orderInfo.qualifiedQty }}／{{ orderInfo.defectiveQty }}</span>
                </el-descriptions-item>
              </el-descriptions>
            </el-card>

            <!-- 正向追溯：批次信息 -->
            <el-card v-if="batchInfo" shadow="never" style="margin-bottom: 16px">
              <div class="section-title">批次信息</div>
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="批次号">
                  <span class="mono">{{ batchInfo.batchNo }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag :type="dictType(BATCH_STATUS, batchInfo.status)" size="small">
                    {{ dictLabel(BATCH_STATUS, batchInfo.status) }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="物料">
                  {{ batchInfo.materialName }}
                  <span class="mono text-muted">（{{ batchInfo.materialCode }}）</span>
                </el-descriptions-item>
                <el-descriptions-item label="数量">
                  <span class="mono">{{ batchInfo.qty }}{{ batchInfo.unit || '' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="供应商">{{ batchInfo.supplier || '—' }}</el-descriptions-item>
                <el-descriptions-item label="入库时间">
                  <span class="mono">{{ batchInfo.inboundTime }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="流向工单" :span="2">
                  <span v-if="result.boundOrderNo" class="mono">{{ result.boundOrderNo }}</span>
                  <span v-else class="text-muted">尚未投产</span>
                </el-descriptions-item>
              </el-descriptions>
            </el-card>

            <!-- 节点流水 -->
            <el-card shadow="never">
              <div class="section-title">
                全链路节点流水
                <span class="section-hint">共 {{ nodes.length }} 个节点，按发生时间排列</span>
              </div>
              <el-timeline v-if="nodes.length">
                <el-timeline-item
                  v-for="(n, i) in nodes"
                  :key="i"
                  :type="nodeType(n)"
                  :timestamp="n.traceTime"
                  placement="top"
                >
                  <div class="node-title">
                    <el-tag :type="nodeType(n)" size="small" effect="light">{{ nodeLabel(n) }}</el-tag>
                    <span class="node-desc">{{ n.nodeDesc }}</span>
                  </div>
                  <div class="node-meta">
                    <span v-if="n.operator">操作人：{{ n.operator }}</span>
                    <span v-if="n.batchNo" class="mono">批次 {{ n.batchNo }}</span>
                    <span v-if="n.orderNo" class="mono">工单 {{ n.orderNo }}</span>
                  </div>
                </el-timeline-item>
              </el-timeline>
              <el-empty v-else description="暂无节点流水" :image-size="70" />
            </el-card>
          </el-col>

          <!-- 右侧：关联批次 + 不良明细 -->
          <el-col :xs="24" :lg="9">
            <el-card shadow="never" style="margin-bottom: 16px">
              <div class="section-title">
                关联物料批次
                <span class="section-hint">{{ batches.length }} 个</span>
              </div>
              <el-table v-if="batches.length" :data="batches" size="small">
                <el-table-column prop="batchNo" label="批次号" min-width="150">
                  <template #default="{ row }">
                    <span class="mono" style="font-size: 12px">{{ row.batchNo }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="materialName" label="物料" min-width="110" show-overflow-tooltip />
                <el-table-column label="状态" width="86">
                  <template #default="{ row }">
                    <el-tag :type="dictType(BATCH_STATUS, row.status)" size="small" effect="plain">
                      {{ dictLabel(BATCH_STATUS, row.status) }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-else description="未关联批次" :image-size="60" />
            </el-card>

            <el-card shadow="never">
              <div class="section-title">
                不良明细
                <span class="section-hint">{{ defects.length }} 条</span>
              </div>
              <el-table v-if="defects.length" :data="defects" size="small">
                <el-table-column prop="defectCode" label="不良代码" min-width="130">
                  <template #default="{ row }">
                    <span class="mono" style="font-size: 12px">{{ row.defectCode }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="不良数" width="76">
                  <template #default="{ row }">
                    <span class="mono" style="color: #cf222e">{{ row.defectiveQty }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="检验" width="86">
                  <template #default="{ row }">
                    <el-tag :type="dictType(INSPECT_RESULT, row.result)" size="small" effect="plain">
                      {{ dictLabel(INSPECT_RESULT, row.result) }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-else description="没有不良记录 —— 这批货质量正常" :image-size="60" />
            </el-card>
          </el-col>
        </el-row>
      </template>
    </div>
  </div>
</template>

<style scoped>
.node-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.node-desc {
  font-size: 13px;
  color: #1b2027;
}

.node-meta {
  margin-top: 4px;
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #8a94a1;
}
</style>
