<script setup>
/**
 * ECharts 轻量包装。
 *
 * 只做三件事，避免每个图表页重复写：按需初始化、option 变化自动更新、容器尺寸变化自动 resize。
 * 不引 vue-echarts：多一层依赖、且它封装的东西这里几十行就够了。
 */
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '280px' }
})

const el = ref(null)
const chart = shallowRef(null)
let observer = null

function render() {
  if (!chart.value) return
  // notMerge=true：筛选项变化时旧系列要清掉，否则会残留上一次的数据
  chart.value.setOption(props.option, true)
}

onMounted(() => {
  chart.value = echarts.init(el.value)
  render()

  // 侧边栏折叠、窗口缩放都会改变容器宽度，图表不会自动跟随，必须手动 resize
  observer = new ResizeObserver(() => chart.value && chart.value.resize())
  observer.observe(el.value)
})

watch(() => props.option, render, { deep: true })

onBeforeUnmount(() => {
  if (observer) observer.disconnect()
  if (chart.value) chart.value.dispose()
})
</script>

<template>
  <div ref="el" :style="{ height, width: '100%' }"></div>
</template>
