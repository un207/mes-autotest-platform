import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import 'element-plus/dist/index.css'
import './styles/global.css'

import App from './App.vue'

const app = createApp(App)

// 中文语言包：分页、表格空数据、日期选择这些默认文案都要是中文
app.use(ElementPlus, { locale: zhCn })

// 图标全局注册，模板里直接用 <el-icon><Search /></el-icon>
for (const [name, comp] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, comp)
}

app.mount('#app')
