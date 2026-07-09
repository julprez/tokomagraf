import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Interceptor para añadir token JWT
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Interceptor para manejar errores de auth
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ── Auth ──

export const auth = {
  register: (data: { name: string; email: string; password: string }) =>
    api.post('/auth/register', data).then((r) => r.data),
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data).then((r) => r.data),
  generateSeed: () =>
    api.post('/auth/generate-seed').then((r) => r.data),
  loginSeed: (data: { words: string[]; name?: string }) =>
    api.post('/auth/login-seed', data).then((r) => r.data),
  me: () => api.get('/auth/me').then((r) => r.data),
  updateProfile: (data: { name?: string; current_password?: string; new_password?: string }) =>
    api.put('/auth/me', data).then((r) => r.data),
}

// ── Portfolio ──

export const portfolio = {
  dashboard: () => api.get('/portfolio/dashboard').then((r) => r.data),
  balances: () => api.get('/portfolio/balances').then((r) => r.data),
  history: (limit = 30) => api.get(`/portfolio/history?limit=${limit}`).then((r) => r.data),
  analysis: () => api.get('/portfolio/analysis').then((r) => r.data),
  summary: () => api.get('/portfolio/summary').then((r) => r.data),
  charts: () => api.get('/portfolio/charts').then((r) => r.data),
}

// ── Operations ──

export const operations = {
  list: (limit = 20) => api.get(`/operations/?limit=${limit}`).then((r) => r.data),
  buy: (data: any) => api.post('/operations/buy', data).then((r) => r.data),
  sell: (data: any) => api.post('/operations/sell', data).then((r) => r.data),
  deposit: (data: any) => api.post('/operations/deposit', data).then((r) => r.data),
  withdraw: (data: any) => api.post('/operations/withdraw', data).then((r) => r.data),
  history: (days = 30) => api.get(`/operations/history?days=${days}`).then((r) => r.data),
  exportCsv: () => api.get('/operations/export', { responseType: 'blob' }).then((r) => r.data),
}

// ── Prices ──

export const prices = {
  btc: () => api.get('/prices/btc').then((r) => r.data),
  detail: () => api.get('/prices/btc/detail').then((r) => r.data),
  chart: (days = 7) => api.get(`/prices/btc/chart?days=${days}`).then((r) => r.data),
}

// ── Alerts ──

export const alerts = {
  list: () => api.get('/alerts/').then((r) => r.data),
  create: (data: { alert_type: string; target_value: number; asset?: string; note?: string }) =>
    api.post('/alerts/', data).then((r) => r.data),
  delete: (id: number) => api.delete(`/alerts/${id}`),
  toggle: (id: number) => api.put(`/alerts/${id}/toggle`).then((r) => r.data),
}

// ── Exchanges ──

export const exchanges = {
  list: () => api.get('/exchanges/').then((r) => r.data),
  create: (data: { name: string; api_key: string; api_secret: string }) =>
    api.post('/exchanges/', data).then((r) => r.data),
  delete: (id: number) => api.delete(`/exchanges/${id}`),
}

// ── Predictions ──

export const predictions = {
  get: () => api.get('/predictions/').then((r) => r.data),
}

// ── DCA ──

export const dca = {
  comparison: () => api.get('/dca/comparison').then((r) => r.data),
  config: () => api.get('/dca/config').then((r) => r.data),
  updateConfig: (data: { frequency?: string; day?: number; active?: boolean }) =>
    api.put('/dca/config', data).then((r) => r.data),
}

export default api
