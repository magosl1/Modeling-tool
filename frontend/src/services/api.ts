import axios, { type AxiosResponse } from 'axios'
import type {
  Project, ProjectCreate, ProjectUpdate,
  HistoricalResponse, AllAssumptions, AssumptionItem, ModuleStatus,
  ProjectionsResponse, RunProjectionResponse,
  ValuationInputCreate, ValuationResult,
  RatiosResponse,
  LoginRequest, RegisterRequest, AuthTokens,
} from '../types/api'

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
          const { data } = await axios.post<AuthTokens>(`${BASE_URL}/auth/refresh`, { refresh_token: refresh })
          localStorage.setItem('access_token', data.access_token)
          localStorage.setItem('refresh_token', data.refresh_token)
          error.config.headers.Authorization = `Bearer ${data.access_token}`
          return api(error.config)
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

// Auth
export const authApi = {
  register: (data: RegisterRequest): Promise<AxiosResponse<AuthTokens>> =>
    api.post('/auth/register', data),
  login: (data: LoginRequest): Promise<AxiosResponse<AuthTokens>> =>
    api.post('/auth/login', data),
}

// Projects
export const projectsApi = {
  list: (): Promise<AxiosResponse<Project[]>> => api.get('/projects'),
  create: (data: ProjectCreate): Promise<AxiosResponse<Project>> => api.post('/projects', data),
  get: (id: string): Promise<AxiosResponse<Project>> => api.get(`/projects/${id}`),
  update: (id: string, data: ProjectUpdate): Promise<AxiosResponse<Project>> => api.put(`/projects/${id}`, data),
  delete: (id: string): Promise<AxiosResponse<void>> => api.delete(`/projects/${id}`),
}

// Historical
export const historicalApi = {
  downloadTemplate: (projectId: string): Promise<AxiosResponse<Blob>> =>
    api.get(`/projects/${projectId}/template/historical`, { responseType: 'blob' }),
  upload: (projectId: string, file: File): Promise<AxiosResponse<{ message: string; years: number[] }>> => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/projects/${projectId}/upload/historical`, form)
  },
  getData: (projectId: string): Promise<AxiosResponse<HistoricalResponse>> =>
    api.get(`/projects/${projectId}/historical`),
}

// Assumptions
export const assumptionsApi = {
  getAll: (projectId: string): Promise<AxiosResponse<AllAssumptions>> =>
    api.get(`/projects/${projectId}/assumptions`),
  getModule: (projectId: string, module: string): Promise<AxiosResponse<AssumptionItem[]>> =>
    api.get(`/projects/${projectId}/assumptions/${module}`),
  saveModule: (projectId: string, module: string, data: AssumptionItem[]): Promise<AxiosResponse<{ message: string }>> =>
    api.put(`/projects/${projectId}/assumptions/${module}`, data),
  getModuleStatus: (projectId: string): Promise<AxiosResponse<ModuleStatus[]>> =>
    api.get(`/projects/${projectId}/modules/status`),
}

// Templates
export const templatesApi = {
  downloadModule: (projectId: string, module: string): Promise<AxiosResponse<Blob>> =>
    api.get(`/projects/${projectId}/template/${module}`, { responseType: 'blob' }),
}

// Projections
export const projectionsApi = {
  get: (projectId: string): Promise<AxiosResponse<ProjectionsResponse>> =>
    api.get(`/projects/${projectId}/projections`),
  run: (projectId: string): Promise<AxiosResponse<RunProjectionResponse>> =>
    api.post(`/projects/${projectId}/projections/run`),
  export: (projectId: string): Promise<AxiosResponse<Blob>> =>
    api.get(`/projects/${projectId}/projections/export`, { responseType: 'blob' }),
}

// Valuation
export const valuationApi = {
  get: (projectId: string): Promise<AxiosResponse<ValuationResult>> =>
    api.get(`/projects/${projectId}/valuation`),
  run: (projectId: string, data: ValuationInputCreate): Promise<AxiosResponse<ValuationResult>> =>
    api.post(`/projects/${projectId}/valuation`, data),
  getSensitivity: (projectId: string): Promise<AxiosResponse<{ sensitivity_table: Record<string, Record<string, string>> }>> =>
    api.get(`/projects/${projectId}/valuation/sensitivity`),
}

// Ratios
export const ratiosApi = {
  get: (projectId: string): Promise<AxiosResponse<RatiosResponse>> =>
    api.get(`/projects/${projectId}/ratios`),
}

export default api
