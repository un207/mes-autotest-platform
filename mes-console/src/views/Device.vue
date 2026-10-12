<script setup>
/**
 * 设备数采监控 —— 看设备上报了什么、哪些被判为不可信、为什么。
 *
 * 这一页是「质量把关」最直观的呈现：同一个列表里既有正常数据也有脏数据，
 * 每条脏数据都带着判定原因和"数值是否入账"的标记。
 * 目的就是让人一眼确认：脏数据没有被静默丢弃，而是被标记、被留痕、可排查。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import api from '../api'
import EChart from '../components/EChart.vue'
import { METRIC, METRIC_OPTIONS, QUALITY_FLAG, QUALITY_FLAG_OPTIONS, dictLabel, dictType } from '../utils/dict'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ pageNum: 1, pageSize: 10, equipmentCode: '', metric: '', qualityFlag: '' })

const abnormal = ref([])
const loadingAbnormal = ref(false)
const abnormalLimit = ref(20)

async function load() {
  loading.value = true
  try {
    const data = await api.device.page(query)
    rows.value = data.records || []
    total.value = data.total || 0
  } catch (err) {
    ElMessage.error(`加载数采记录失败：${err.message}`)
  } finally {
    loading.value = false
  }
}

async function loadAbnormal() {
  loadingAbnormal.value = true
  try {
    abnormal.value = await api.device.abnormal(abnormalLimit.value)
  } catch (err) {
    ElMessage.error(`加载异常记录失败：${err.message}`)
  } finally {
    loadingAbnormal.value = false
  }
}

function search() {
  query.pageNum = 1
  load()
}

function resetQuery() {
  query.equipmentCode = ''
  query.metric = ''
  query.qualityFlag = ''
  search()
}

onMounted(() => {
  load()
  loadAbnormal()
})

// ---------------------------------------------------------------- 判定原因归类
// 把后端给的原因文本归到三类，便于统计"哪一类问题最多"
function reasonCategory(msg) {
  if (!msg) return '其他'
  if (msg.includes('解析')) return '无法解析'
  if (msg.includes('区间')) return '超出工况区间'
  if (msg.includes('时间')) return '采集时间异常'
  return '其他'
}

const reasonStats = computed(() => {
  const map = {}
  abnormal.value.forEach((r) => {
    const k = reasonCategory(r.qualityMessage)
    map[k] = (map[k] || 0) + 1
  })
  return Object.entries(map).map(([name, value]) => ({ name, value }))
})

const reasonOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 条（{d}%）' },
  legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 11, color: '#5b6572' } },
  series: [
    {
      type: 'pie',
      radius: ['40%', '66%'],
      center: ['50%', '44%'],
      label: { show: false },
      data: reasonStats.value
    }
  ]
}))

// ---------------------------------------------------------------- 指标分布
const metricStats = computed(() => {
  const map = {}
  abnormal.value.forEach((r) => {
    const k = METRIC[r.metric]?.label || r.metric
    map[k] = (map[k] || 0) + 1
  })
  return map
})

const metricLabel = (m) => (METRIC[m] ? METRIC[m].label : m)

/** 是否入账：异常数据（BAD）不入账，可疑数据（SUSPECT）仍留档 */
const isRecorded = (row) => row.metricValue !== null && row.metricValue !== undefined
</script>

<template>
  <div class="page">
    <!-- 概览 -->
    <div class="metric-grid" style="margin-bottom: 16px">
      <div class="metric-card">
        <div class="label">数采记录总数</div>
        <div class="value">{{ total }}</div>
      </div>
      <div class="metric-card">
        <div class="label">异常/可疑（近期）</div>
        <div class="value" :class="abnormal.length ? 'is-warn' : 'is-good'">{{ abnormal.length }}</div>
      </div>
      <div class="metric-card">
        <div class="label">无法解析</div>
        <div class="value">{{ reasonStats.find((r) => r.name === '无法解析')?.value ?? 0 }}</div>
      </div>
      <div class="metric-card">
        <div class="label">超出工况区间</div>
        <div class="value">{{ reasonStats.find((r) => r.name === '超出工况区间')?.value ?? 0 }}</div>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never">
          <div class="toolbar" style="margin-bottom: 12px">
            <el-input
              v-model="query.equipmentCode"
              placeholder="按设备编号筛选"
              clearable
              style="width: 190px"
              @keyup.enter="search"
            />
            <el-select v-model="query.metric" placeholder="全部指标" clearable style="width: 130px" @change="search">
              <el-option v-for="o in METRIC_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-select v-model="query.qualityFlag" placeholder="全部质量" clearable style="width: 130px" @change="search">
              <el-option v-for="o in QUALITY_FLAG_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-button type="primary" :icon="'Search'" @click="search">查询</el-button>
            <el-button :icon="'RefreshLeft'" @click="resetQuery">重置</el-button>
          </div>

          <el-table v-loading="loading" :data="rows" size="default" empty-text="暂无数采记录">
            <el-table-column prop="equipmentCode" label="设备编号" width="150">
              <template #default="{ row }"><span class="mono">{{ row.equipmentCode }}</span></template>
            </el-table-column>
            <el-table-column label="指标" width="90">
              <template #default="{ row }">{{ metricLabel(row.metric) }}</template>
            </el-table-column>
            <el-table-column prop="rawValue" label="原始值" width="110">
              <template #default="{ row }"><span class="mono">{{ row.rawValue }}</span></template>
            </el-table-column>
            <el-table-column label="解析值" width="110">
              <template #default="{ row }">
                <span v-if="isRecorded(row)" class="mono">{{ row.metricValue }}</span>
                <el-tag v-else type="danger" size="small" effect="plain">未入账</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="质量" width="90">
              <template #default="{ row }">
                <el-tag :type="dictType(QUALITY_FLAG, row.qualityFlag)" size="small">
                  {{ dictLabel(QUALITY_FLAG, row.qualityFlag) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="qualityMessage" label="判定说明" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.qualityMessage">{{ row.qualityMessage }}</span>
                <span v-else class="text-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column prop="collectTime" label="采集时间" width="160">
              <template #default="{ row }"><span class="mono">{{ row.collectTime }}</span></template>
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
        <el-card shadow="never" style="margin-bottom: 16px">
          <div class="section-title">
            异常原因分布
            <span class="section-hint">近 {{ abnormal.length }} 条</span>
          </div>
          <EChart v-if="reasonStats.length" :option="reasonOption" height="230px" />
          <el-empty v-else description="近期没有异常数据" :image-size="70" />
        </el-card>

        <el-card shadow="never">
          <div class="section-title">
            异常数据排查
            <span class="section-hint">脏数据留痕，可逐条回溯</span>
          </div>
          <div class="toolbar" style="margin-bottom: 10px">
            <el-select v-model="abnormalLimit" size="small" style="width: 110px" @change="loadAbnormal">
              <el-option :value="10" label="最近 10 条" />
              <el-option :value="20" label="最近 20 条" />
              <el-option :value="50" label="最近 50 条" />
            </el-select>
            <el-button size="small" :icon="'Refresh'" @click="loadAbnormal">刷新</el-button>
          </div>
          <div v-loading="loadingAbnormal" class="abnormal-list">
            <div v-for="(r, i) in abnormal" :key="i" class="abnormal-item">
              <div class="ai-head">
                <el-tag :type="dictType(QUALITY_FLAG, r.qualityFlag)" size="small" effect="light">
                  {{ dictLabel(QUALITY_FLAG, r.qualityFlag) }}
                </el-tag>
                <span class="mono ai-eq">{{ r.equipmentCode }}</span>
                <span class="text-muted ai-metric">{{ metricLabel(r.metric) }}</span>
              </div>
              <div class="ai-body">
                原始值 <span class="mono">{{ r.rawValue }}</span>
                ·
                <span v-if="isRecorded(r)">已入账 {{ r.metricValue }}</span>
                <span v-else style="color: #cf222e">未入账</span>
              </div>
              <div class="ai-reason">{{ r.qualityMessage || '（无说明）' }}</div>
              <div class="ai-time mono">{{ r.collectTime }}</div>
            </div>
            <el-empty v-if="!loadingAbnormal && !abnormal.length" description="暂无异常数据" :image-size="60" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.abnormal-list {
  max-height: 520px;
  overflow-y: auto;
}

.abnormal-item {
  padding: 10px 12px;
  border: 1px solid #eef1f5;
  border-radius: 8px;
  margin-bottom: 8px;
  background: #fafbfc;
}

.ai-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
}

.ai-eq {
  font-size: 12px;
  color: #5b6572;
}

.ai-metric {
  font-size: 12px;
  margin-left: auto;
}

.ai-body {
  font-size: 12.5px;
  color: #3a4552;
}

.ai-reason {
  font-size: 12px;
  color: #9a6700;
  margin-top: 3px;
  line-height: 1.5;
}

.ai-time {
  font-size: 11px;
  color: #8a94a1;
  margin-top: 3px;
}
</style>
