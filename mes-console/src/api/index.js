/**
 * MES 接口封装。
 *
 * 三件事在这里一次做完，页面里就不用重复处理：
 *   1. 统一契约：MES 所有已路由的请求都返回 HTTP 200，业务结果在 body.code
 *      （0 成功 / 40000 参数 / 40400 不存在 / 40900 状态冲突）。
 *      这里把 code != 0 统一转成异常抛出，页面只需要处理"成功"和"失败"两种分支。
 *   2. 带上 traceId：MES 每个响应都带，出错时一并带出 ——
 *      拿着它去后端日志里搜，能直接定位到那一次请求，这是排查线上问题最快的路径。
 *   3. 参数拼装：把分页、过滤这些重复劳动收在这里。
 *
 * 请求走相对路径 /api，开发期由 vite proxy 转发到后端，避免 CORS 配置散落在前端代码里。
 */

const BASE = import.meta.env.VITE_API_BASE || ''

export class ApiError extends Error {
  constructor(message, { code, httpStatus, traceId, url } = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.httpStatus = httpStatus
    this.traceId = traceId
    this.url = url
  }

  /** 给用户看的简短描述，含 traceId 便于报障。 */
  get detail() {
    const parts = []
    if (this.code !== undefined) parts.push(`code=${this.code}`)
    if (this.httpStatus && this.httpStatus !== 200) parts.push(`HTTP=${this.httpStatus}`)
    if (this.traceId) parts.push(`traceId=${this.traceId}`)
    return parts.join(' · ')
  }
}

function buildQuery(params) {
  if (!params) return ''
  const usp = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return
    usp.append(k, v)
  })
  const s = usp.toString()
  return s ? `?${s}` : ''
}

async function request(path, { method = 'GET', body, params } = {}) {
  const url = `${BASE}${path}${buildQuery(params)}`
  let resp
  try {
    resp = await fetch(url, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json; charset=UTF-8' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined
    })
  } catch (err) {
    // 网络层失败（后端没起、端口不通）—— 给出可操作的提示，而不是笼统的 "Failed to fetch"
    throw new ApiError(`无法连接后端（${err.message}）`, { url })
  }

  let payload = null
  const text = await resp.text()
  try {
    payload = text ? JSON.parse(text) : null
  } catch {
    throw new ApiError('后端返回的不是合法 JSON', {
      httpStatus: resp.status,
      traceId: resp.headers.get('X-Request-Id'),
      url
    })
  }

  const traceId = payload?.traceId || resp.headers.get('X-Request-Id')

  if (resp.status !== 200) {
    throw new ApiError(payload?.message || `请求失败（HTTP ${resp.status}）`, {
      code: payload?.code,
      httpStatus: resp.status,
      traceId,
      url
    })
  }

  if (payload?.code !== 0) {
    throw new ApiError(payload?.message || '业务处理失败', {
      code: payload?.code,
      httpStatus: resp.status,
      traceId,
      url
    })
  }

  return payload.data
}

/** 去掉空值字段，避免把空串当成有效参数发出去。 */
function clean(obj) {
  const out = {}
  Object.entries(obj || {}).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return
    out[k] = v
  })
  return out
}

export const api = {
  // ---------------------------------------------------------------- 自检
  health: () => request('/api/health'),
  ready: () => request('/api/ready'),

  // ---------------------------------------------------------------- 工单
  workOrder: {
    page: (params) => request('/api/work-orders', { params: clean(params) }),
    detail: (orderNo) => request(`/api/work-orders/${encodeURIComponent(orderNo)}`),
    reports: (orderNo) => request(`/api/work-orders/${encodeURIComponent(orderNo)}/reports`),
    create: (body) => request('/api/work-orders', { method: 'POST', body: clean(body) }),
    dispatch: (orderNo, body) =>
      request(`/api/work-orders/${encodeURIComponent(orderNo)}/dispatch`, {
        method: 'PUT',
        body: clean(body)
      }),
    report: (orderNo, body) =>
      request(`/api/work-orders/${encodeURIComponent(orderNo)}/reports`, {
        method: 'POST',
        body: clean(body)
      }),
    close: (orderNo, body) =>
      request(`/api/work-orders/${encodeURIComponent(orderNo)}/close`, {
        method: 'PUT',
        body: clean(body)
      })
  },

  // ---------------------------------------------------------------- 质量
  quality: {
    page: (params) => request('/api/quality-inspections', { params: clean(params) }),
    detail: (inspectNo) => request(`/api/quality-inspections/${encodeURIComponent(inspectNo)}`),
    create: (body) => request('/api/quality-inspections', { method: 'POST', body: clean(body) }),
    defectSummary: () => request('/api/quality-inspections/defect-summary'),
    defectsByOrder: (orderNo) =>
      request(`/api/quality-inspections/defects/${encodeURIComponent(orderNo)}`)
  },

  // ---------------------------------------------------------------- 物料与追溯
  material: {
    page: (params) => request('/api/material-batches', { params: clean(params) }),
    detail: (batchNo) => request(`/api/material-batches/${encodeURIComponent(batchNo)}`),
    byOrder: (orderNo) => request(`/api/material-batches/by-order/${encodeURIComponent(orderNo)}`),
    create: (body) => request('/api/material-batches', { method: 'POST', body: clean(body) }),
    bind: (batchNo, orderNo) =>
      request(`/api/material-batches/${encodeURIComponent(batchNo)}/bind`, {
        method: 'PUT',
        params: { orderNo }
      }),
    outbound: (batchNo, operator) =>
      request(`/api/material-batches/${encodeURIComponent(batchNo)}/outbound`, {
        method: 'PUT',
        params: clean({ operator })
      })
  },

  trace: {
    byBatch: (batchNo) => request(`/api/traces/batch/${encodeURIComponent(batchNo)}`),
    byOrder: (orderNo) => request(`/api/traces/order/${encodeURIComponent(orderNo)}`)
  },

  // ---------------------------------------------------------------- 设备数采
  device: {
    page: (params) => request('/api/device-data', { params: clean(params) }),
    abnormal: (limit = 50) => request('/api/device-data/abnormal', { params: { limit } }),
    report: (body) => request('/api/device-data', { method: 'POST', body: clean(body) }),
    reportBatch: (list) => request('/api/device-data/batch', { method: 'POST', body: list })
  },

  // ---------------------------------------------------------------- 统计
  stats: {
    overview: () => request('/api/stats/overview'),
    production: (params) => request('/api/stats/production', { params: clean(params) }),
    yieldOrders: (limit = 10) => request('/api/stats/yield/orders', { params: { limit } })
  }
}

export default api
