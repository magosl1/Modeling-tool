import axios from 'axios'

const BASE_URL = '/api/v1'

const api = axios.create({ baseURL: BASE_URL })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    if (error.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const { data } = await axios.post(`${BASE_URL}/auth/refresh`, { refresh_token: refresh })
          localStorage.setItem('access_token', data.access_token)
          localStorage.setItem('refresh_token', data.refresh_token)
          error.config.headers.Authorization = `Bearer ${data.access_token}`
          return api(error.config)
        } catch {
          localStorage.clear()
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

// Auth
export const authApi = {
  register: (data: { email: string; password: string; name: string }) =>
    api.post('/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
}

// Projects
export const projectsApi = {
  list: () => api.get('/projects'),
  create: (data: any) => api.post('/projects', data),
  get: (id: string) => api.get(`/projects/${id}`),
  update: (id: string, data: any) => api.put(`/projects/${id}`, data),
  delete: (id: string) => api.delete(`/projects/${id}`),
}

// Historical
export const historicalApi = {
  downloadTemplate: (projectId: string) =>
    api.get(`/projects/${projectId}/template/historical`, { responseType: 'blob' }),
  upload: (projectId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/projects/${projectId}/upload/historical`, form)
  },
  getData: (projectId: string) => api.get(`/projects/${projectId}/historical`),
}

// Assumptions
export const assumptionsApi = {
  getAll: (projectId: string) => api.get(`/projects/${projectId}/assumptions`),
  getModule: (projectId: string, module: string) =>
    api.get(`/projects/${projectId}/assumptions/${module}`),
  saveModule: (projectId: string, module: string, data: any[]) =>
    api.put(`/projects/${projectId}/assumptions/${module}`, data),
  getModuleStatus: (projectId: string) =>
    api.get(`/projects/${projectId}/modules/status`),
}

// Templates
export const templatesApi = {
  downloadModule: (projectId: string, module: string) =>
    api.get(`/projects/${projectId}/template/${module}`, { responseType: 'blob' }),
}

// Projections
export const projectionsApi = {
  get: (projectId: string) => api.get(`/projects/${projectId}/projections`),
  run: (projectId: string) => api.post(`/projects/${projectId}/projections/run`),
  export: (projectId: string) =>
    api.get(`/projects/${projectId}/projections/export`, { responseType: 'blob' }),
}

// Valuation
export const valuationApi = {
  get: (projectId: string) => api.get(`/projects/${projectId}/valuation`),
  run: (projectId: string, data: any) => api.post(`/projects/${projectId}/valuation`, data),
  getSensitivity: (projectId: string) => api.get(`/projects/${projectId}/valuation/sensitivity`),
}

// Ratios
export const ratiosApi = {
  get: (projectId: string) => api.get(`/projects/${projectId}/ratios`),
}

export default api
