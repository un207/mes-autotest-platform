import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 后端地址：换环境时用 MES_BASE_URL 覆盖，不用改代码
const backend = process.env.MES_BASE_URL || 'http://127.0.0.1:8080'
const proxy = {
  '/api': { target: backend, changeOrigin: true }
}

// 开发期用 proxy 转发 /api 到后端，前端代码里统一写相对路径 ——
// 好处是不用在前端配 CORS（虽然后端已开白名单），也不会因为换环境改代码。
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy
  },
  // preview 是给"构建产物"用的：它同样需要代理，
  // 否则打开构建好的页面会因为拿不到 /api 而全部报错 —— 那样验证不到真实产物。
  preview: {
    port: 4173,
    proxy
  },
  build: {
    outDir: 'dist',
    // 构建产物里的资源用相对路径，这样丢到任意静态目录都能打开（包括 file:// 预览）
    assetsDir: 'assets',
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        // 拆 vendor：这三个库体积大且极少变动，单独分包后浏览器可以长期缓存，
        // 改业务代码不会让用户重新下载它们。不拆的话首屏要拉一个 2MB+ 的单包。
        manualChunks: {
          vue: ['vue'],
          'element-plus': ['element-plus', '@element-plus/icons-vue'],
          echarts: ['echarts']
        }
      }
    }
  }
})
