import axios, { type AxiosResponse } from 'axios'
import type {
  Project, ProjectCreate, ProjectUpdate,
  Entity, EntityCreate, EntityUpdate,
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

// Entities (Phase 0 — Universal Platform)
export const entitiesApi = {
  list: (projectId: string): Promise<AxiosResponse<Entity[]>> =>
    api.get(`/projects/${projectId}/entities`),
  create: (projectId: string, data: EntityCreate): Promise<AxiosResponse<Entity>> =>
    api.post(`/projects/${projectId}/entities`, data),
  get: (entityId: string): Promise<AxiosResponse<Entity>> =>
    api.get(`/entities/${entityId}`),
  update: (entityId: string, data: EntityUpdate): Promise<AxiosResponse<Entity>> =>
    api.put(`/entities/${entityId}`, data),
  delete: (entityId: string): Promise<AxiosResponse<void>> =>
    api.delete(`/entities/${entityId}`),
  clone: (entityId: string, data: { new_name: string; overrides?: Record<string, unknown> }): Promise<AxiosResponse<Entity>> =>
    api.post(`/entities/${entityId}/clone`, data),
  bulkCreate: (projectId: string, data: { template: EntityCreate; count: number; naming_pattern?: string }): Promise<AxiosResponse<Entity[]>> =>
    api.post(`/projects/${projectId}/entities/bulk-create`, data),
  getHistorical: (entityId: string): Promise<AxiosResponse<HistoricalResponse>> =>
    api.get(`/entities/${entityId}/historical`),
  getProjections: (entityId: string, scenarioId?: string): Promise<AxiosResponse<Record<string, Record<string, Record<string, string>>>>> =>
    api.get(`/entities/${entityId}/projections`, { params: scenarioId ? { scenario_id: scenarioId } : {} }),
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

// Block 1 — Scenarios
export const scenariosApi = {
  list: (projectId: string) => api.get(`/projects/${projectId}/scenarios`),
  create: (projectId: string, data: any) => api.post(`/projects/${projectId}/scenarios`, data),
  activate: (projectId: string, scenarioId: string) => api.post(`/projects/${projectId}/scenarios/${scenarioId}/activate`),
  copy: (projectId: string, scenarioId: string) => api.post(`/projects/${projectId}/scenarios/${scenarioId}/copy`),
  delete: (projectId: string, scenarioId: string) => api.delete(`/projects/${projectId}/scenarios/${scenarioId}`),
}

// Block 2 — Debt Schedule (Revolver + Term Loans)
export const debtApi = {
  getRevolver: (projectId: string, scenarioId?: string) =>
    api.get(`/projects/${projectId}/debt/revolver`, { params: { scenario_id: scenarioId } }),
  saveRevolver: (projectId: string, data: any) =>
    api.put(`/projects/${projectId}/debt/revolver`, data),
  getTranches: (projectId: string, scenarioId?: string) =>
    api.get(`/projects/${projectId}/debt/tranches`, { params: { scenario_id: scenarioId } }),
  saveTranches: (projectId: string, data: any[], scenarioId?: string) =>
    api.put(`/projects/${projectId}/debt/tranches`, data, { params: { scenario_id: scenarioId } }),
}

// Block 3 — FX Rates
export const fxApi = {
  get: (projectId: string) => api.get(`/projects/${projectId}/fx`),
  save: (projectId: string, data: any) => api.put(`/projects/${projectId}/fx`, data),
}

// Block 4 — Monte Carlo Simulation
export const simulationApi = {
  run: (projectId: string, data: any) => api.post(`/projects/${projectId}/monte-carlo`, data),
  getLatest: (projectId: string, scenarioId?: string) =>
    api.get(`/projects/${projectId}/monte-carlo/latest`, { params: { scenario_id: scenarioId } }),
}

// Block 5 — Collaboration / Sharing
export const sharingApi = {
  list: (projectId: string) => api.get(`/projects/${projectId}/share`),
  share: (projectId: string, data: { email: string; role: string }) =>
    api.post(`/projects/${projectId}/share`, data),
  revoke: (projectId: string, userId: string) =>
    api.delete(`/projects/${projectId}/share/${userId}`),
  getSharedWithMe: () => api.get('/projects/shared-with-me'),
}

// Block 6 — External Curves / Indices
export const curvesApi = {
  get: (projectId: string) => api.get(`/projects/${projectId}/curves`),
  save: (projectId: string, data: Record<string, { is_percentage: boolean, values: Record<string, number> }>) => 
    api.put(`/projects/${projectId}/curves`, data),
}

export default api
