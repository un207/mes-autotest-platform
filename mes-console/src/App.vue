<script setup>
import { computed, onMounted, onUnmounted, ref, shallowRef } from 'vue'
import { ElMessage } from 'element-plus'

import api from './api'
import Overview from './views/Overview.vue'
import WorkOrders from './views/WorkOrders.vue'
import Quality from './views/Quality.vue'
import Material from './views/Material.vue'
import Trace from './views/Trace.vue'
import Device from './views/Device.vue'

// 用 shallowRef 而不是 ref：组件对象不需要深层响应式，浅层足够且避免无谓开销
const views = {
  overview: { comp: shallowRef(Overview), label: '总览', icon: 'DataLine' },
  workorders: { comp: shallowRef(WorkOrders), label: '工单管理', icon: 'Tickets' },
  quality: { comp: shallowRef(Quality), label: '质量管理', icon: 'Checked' },
  material: { comp: shallowRef(Material), label: '物料批次', icon: 'Box' },
  trace: { comp: shallowRef(Trace), label: '追溯查询', icon: 'Connection' },
  device: { comp: shallowRef(Device), label: '设备数采', icon: 'Cpu' }
}

const current = ref('overview')
const currentComp = computed(() => views[current.value].comp.value)

// ---- 后端连通状态：顶部常驻指示灯 ----
const conn = ref({ state: 'checking', text: '检查中…', db: '' })
let timer = null

async function checkConn(notify = false) {
  try {
    const data = await api.ready()
    conn.value = {
      state: 'up',
      text: '后端已连接',
      db: `${data.dbProduct || ''}`
    }
    if (notify) ElMessage.success('后端连接正常')
  } catch (err) {
    conn.value = { state: 'down', text: '后端不可用', db: err.message }
    if (notify) ElMessage.error(`后端连接失败：${err.message}`)
  }
}

onMounted(() => {
  checkConn()
  // 30 秒轮一次，够用又不至于频繁打扰
  timer = setInterval(() => checkConn(), 30000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

const connTagType = computed(() =>
  conn.value.state === 'up' ? 'success' : conn.value.state === 'down' ? 'danger' : 'info'
)
</script>

<template>
  <el-container class="layout">
    <el-aside width="212px" class="sidebar">
      <div class="brand">
        <div class="brand-mark">MES</div>
        <div class="brand-text">
          <div class="brand-title">迷你 MES 管理台</div>
          <div class="brand-sub">制造执行系统</div>
        </div>
      </div>

      <el-menu :default-active="current" class="nav" @select="(k) => (current = k)">
        <el-menu-item v-for="(v, key) in views" :key="key" :index="key">
          <el-icon><component :is="v.icon" /></el-icon>
          <span>{{ v.label }}</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-foot">
        <div class="foot-line">被测对象：mes-platform</div>
        <div class="foot-line">自动化用例：99 条</div>
      </div>
    </el-aside>

    <el-container>
      <el-header height="56px" class="topbar">
        <div class="topbar-title">{{ views[current].label }}</div>
        <div class="topbar-right">
          <el-tag :type="connTagType" size="small" effect="light" class="conn-tag">
            <span class="conn-dot" :class="conn.state"></span>
            {{ conn.text }}
          </el-tag>
          <span v-if="conn.db" class="mono text-muted db-text">{{ conn.db }}</span>
          <el-button size="small" :icon="'Refresh'" @click="checkConn(true)">重新检测</el-button>
        </div>
      </el-header>

      <el-main class="content">
        <component :is="currentComp" @navigate="(k) => (current = k)" />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}

.sidebar {
  background: var(--mes-sidebar);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 16px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.brand-mark {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 8px;
  background: var(--mes-sidebar-active);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 0.02em;
}

.brand-title {
  color: #fff;
  font-size: 14px;
  font-weight: 500;
}

.brand-sub {
  color: rgba(255, 255, 255, 0.45);
  font-size: 11.5px;
  margin-top: 2px;
}

.nav {
  flex: 1;
  border-right: none;
  background: transparent;
  padding: 10px 8px;
  overflow-y: auto;
}

.nav :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.72);
  height: 42px;
  line-height: 42px;
  border-radius: 8px;
  margin-bottom: 2px;
}

.nav :deep(.el-menu-item:hover) {
  background: var(--mes-sidebar-hover);
  color: #fff;
}

.nav :deep(.el-menu-item.is-active) {
  background: var(--mes-sidebar-active);
  color: #fff;
  font-weight: 500;
}

.sidebar-foot {
  padding: 14px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.foot-line {
  color: rgba(255, 255, 255, 0.4);
  font-size: 11.5px;
  line-height: 1.8;
}

.topbar {
  background: #fff;
  border-bottom: 1px solid #e8ecf1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.topbar-title {
  font-size: 15px;
  font-weight: 600;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.conn-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.conn-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #8a94a1;
  display: inline-block;
}

.conn-dot.up {
  background: #1a7f37;
}

.conn-dot.down {
  background: #cf222e;
}

.db-text {
  font-size: 12px;
}

.content {
  padding: 0;
  background: var(--mes-bg);
  overflow-y: auto;
}
</style>
