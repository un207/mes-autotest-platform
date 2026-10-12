<script setup>
/**
 * 总览页 —— 一屏看清平台当前状态。
 *
 * 数据全部来自统计接口（跨表聚合由后端算好），前端不做二次计算 ——
 * 口径只在一个地方定义，界面上的数字和接口、报表永远一致。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import api from '../api'
import EChart from '../components/EChart.vue'
import { METRIC, num, percent, rateClass, runStatusLabel } from '../utils/dict'

const loading = ref(false)
const overview = ref({})
const production = ref([])
const yieldRanking = ref([])
const deviceRows = ref([])

async function load() {
  loading.value = true
  try {
    // 四个请求互不依赖，并行发，页面一次刷新到位
    const [ov, prod, ranking, abnormal] = await Promise.allSettled([
      api.stats.overview(),
      api.stats.production(),
      api.stats.yieldOrders(5),
      api.device.abnormal(8)
    ])

    if (ov.status === 'fulfilled') overview.value = ov.value || {}
    if (prod.status === 'fulfilled') production.value = prod.value || []
    if (ranking.status === 'fulfilled') yieldRanking.value = ranking.value || []
    if (abnormal.status === 'fulfilled') deviceRows.value = abnormal.value || []

    // 部分失败也要说清楚是哪一项，不能整页静默
    const failed = [ov, prod, ranking, abnormal].filter((r) => r.status === 'rejected')
    if (failed.length) {
      ElMessage.warning(`有 ${failed.length} 项统计未能加载：${failed[0].reason?.message || '未知原因'}`)
    }
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ---------------------------------------------------------------- 图表
const productionOption = computed(() => {
  const rows = production.value.slice(-14)
  return {
    grid: { left: 48, right: 20, top: 36, bottom: 30 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['计划产量', '实际报工', '合格数'], top: 0, itemWidth: 12, itemHeight: 8 },
    xAxis: {
      type: 'category',
      data: rows.map((r) => r.statDate),
      axisLabel: { fontSize: 11, color: '#8a94a1' },
      axisLine: { lineStyle: { color: '#e8ecf1' } }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f0f3f7' } },
      axisLabel: { fontSize: 11, color: '#8a94a1' }
    },
    series: [
      {
        name: '计划产量',
        type: 'bar',
        data: rows.map((r) => r.planQty),
        itemStyle: { color: '#c3cbd4', borderRadius: [3, 3, 0, 0] },
        barMaxWidth: 18
      },
      {
        name: '实际报工',
        type: 'bar',
        data: rows.map((r) => r.finishedQty),
        itemStyle: { color: '#2f6feb', borderRadius: [3, 3, 0, 0] },
        barMaxWidth: 18
      },
      {
        name: '合格数',
        type: 'line',
        data: rows.map((r) => r.qualifiedQty),
        smooth: true,
        symbolSize: 6,
        lineStyle: { width: 2, color: '#1a7f37' },
        itemStyle: { color: '#1a7f37' }
      }
    ]
  }
})

const rankingOption = computed(() => {
  const rows = [...yieldRanking.value].reverse()
  return {
    grid: { left: 130, right: 46, top: 10, bottom: 22 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (ps) => {
        const p = ps[0]
        const row = rows[p.dataIndex]
        return `${p.name}<br/>良率 ${row.yieldRate}%<br/>报工 ${row.finishedQty}／合格 ${row.qualifiedQty}／不良 ${row.defectiveQty}`
      }
    },
    xAxis: {
      type: 'value',
      max: 100,
      splitLine: { lineStyle: { color: '#f0f3f7' } },
      axisLabel: { fontSize: 11, color: '#8a94a1', formatter: '{value}%' }
    },
    yAxis: {
      type: 'category',
      data: rows.map((r) => r.orderNo),
      axisLabel: { fontSize: 11, color: '#5b6572', fontFamily: 'monospace' },
      axisLine: { lineStyle: { color: '#e8ecf1' } }
    },
    series: [
      {
        type: 'bar',
        data: rows.map((r) => ({
          value: Number(r.yieldRate),
          // 低良率标红：这张图的意义就是一眼找到最差的
          itemStyle: {
            color: Number(r.yieldRate) < 90 ? '#cf222e' : Number(r.yieldRate) < 97 ? '#ef9f27' : '#1a7f37',
            borderRadius: [0, 3, 3, 0]
          }
        })),
        barMaxWidth: 16,
        label: {
          show: true,
          position: 'right',
          fontSize: 11,
          color: '#5b6572',
          formatter: '{c}%'
        }
      }
    ]
  }
})

const deviceMetricLabel = (metric) => (METRIC[metric] ? METRIC[metric].label : metric)
</script>

<template>
  <div class="page" v-loading="loading">
    <!-- 顶部操作 -->
    <div class="toolbar">
      <span class="section-hint">
        数据来自统计接口跨表聚合。良率 = 合格数 ÷ 报工数，由后端统一计算。
      </span>
      <div class="spacer"></div>
      <el-button :icon="'Refresh'" @click="load">刷新</el-button>
    </div>

    <!-- 核心指标 -->
    <div class="metric-grid" style="margin-bottom: 18px">
      <div class="metric-card">
        <div class="label">工单总数</div>
        <div class="value">{{ num(overview.totalOrders, 0) }}</div>
      </div>
      <div class="metric-card">
        <div class="label">在产工单</div>
        <div class="value">{{ num(overview.openOrders, 0) }}</div>
      </div>
      <div class="metric-card">
        <div class="label">已关闭</div>
        <div class="value">{{ num(overview.closedOrders, 0) }}</div>
      </div>
      <div class="metric-card">
        <div class="label">计划总产量</div>
        <div class="value">{{ num(overview.totalPlanQty, 0) }}</div>
      </div>
      <div class="metric-card">
        <div class="label">累计报工</div>
        <div class="value">{{ num(overview.totalFinishedQty, 0) }}</div>
      </div>
      <div class="metric-card">
        <div class="label">综合良率</div>
        <div class="value" :class="rateClass(overview.yieldRate)">
          {{ num(overview.yieldRate, 2) }}<small>%</small>
        </div>
      </div>
      <div class="metric-card">
        <div class="label">累计不良</div>
        <div class="value" :class="overview.totalDefectiveQty ? 'is-bad' : ''">
          {{ num(overview.totalDefectiveQty, 0) }}
        </div>
      </div>
      <div class="metric-card">
        <div class="label">数采记录</div>
        <div class="value">{{ num(overview.deviceDataCount, 0) }}</div>
      </div>
      <div class="metric-card">
        <div class="label">其中异常/可疑</div>
        <div class="value" :class="overview.deviceAbnormalCount ? 'is-warn' : ''">
          {{ num(overview.deviceAbnormalCount, 0) }}
        </div>
      </div>
      <div class="metric-card">
        <div class="label">质检记录</div>
        <div class="value">
          {{ num(overview.inspectionCount, 0) }}
          <small v-if="overview.inspectionFailCount" class="fail-hint">
            不合格 {{ overview.inspectionFailCount }}
          </small>
        </div>
      </div>
    </div>

    <!-- 图表区 -->
    <el-row :gutter="16">
      <el-col :xs="24" :lg="15">
        <el-card shadow="never" class="chart-card">
          <div class="section-title">
            产量日报
            <span class="section-hint">按日期汇总计划／报工／合格；取最近 14 天</span>
          </div>
          <EChart :option="productionOption" height="300px" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="9">
        <el-card shadow="never" class="chart-card">
          <div class="section-title">
            低良率工单排行
            <span class="section-hint">良率最低的 5 张</span>
          </div>
          <EChart v-if="yieldRanking.length" :option="rankingOption" height="300px" />
          <el-empty v-else description="暂无有报工的工单" :image-size="70" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 异常数采 -->
    <el-card shadow="never" class="chart-card" style="margin-top: 16px">
      <div class="section-title">
        异常数采记录
        <span class="section-hint">
          被质量把关拦下的数据 —— 脏数据不静默丢弃，一律留痕待排查
        </span>
      </div>
      <el-table :data="deviceRows" size="small" empty-text="暂无异常数据">
        <el-table-column prop="equipmentCode" label="设备编号" width="150">
          <template #default="{ row }"><span class="mono">{{ row.equipmentCode }}</span></template>
        </el-table-column>
        <el-table-column label="指标" width="110">
          <template #default="{ row }">{{ deviceMetricLabel(row.metric) }}</template>
        </el-table-column>
        <el-table-column prop="rawValue" label="原始上报值" width="130">
          <template #default="{ row }"><span class="mono">{{ row.rawValue }}</span></template>
        </el-table-column>
        <el-table-column label="数值是否入账" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.metricValue !== null && row.metricValue !== undefined" type="info" size="small" effect="plain">
              已入账 {{ row.metricValue }}
            </el-tag>
            <el-tag v-else type="danger" size="small" effect="plain">未入账</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="数据质量" width="100">
          <template #default="{ row }">
            <el-tag :type="row.qualityFlag === 'BAD' ? 'danger' : 'warning'" size="small">
              {{ row.qualityFlag === 'BAD' ? '异常' : '可疑' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="qualityMessage" label="判定原因" min-width="220" show-overflow-tooltip />
        <el-table-column prop="collectTime" label="采集时间" width="165">
          <template #default="{ row }"><span class="mono">{{ row.collectTime }}</span></template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.chart-card :deep(.el-card__body) {
  padding: 16px 18px;
}

.fail-hint {
  font-size: 12px;
  font-weight: 400;
  color: #cf222e;
  margin-left: 6px;
}
</style>
