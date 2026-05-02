import axios, { type AxiosResponse } from 'axios'
import type {
  Project, ProjectCreate, ProjectUpdate,
  Entity, EntityCreate, EntityUpdate,
  HistoricalResponse, AllAssumptions, AssumptionItem, ModuleStatus,
  ProjectionsResponse, RunProjectionResponse,
  ValuationInputCreate, ValuationResult,
  RatiosResponse,
  LoginRequest, RegisterRequest, AuthTokens,
  ConsolidatedResponse, IntercompanyElimination, EliminationCreate,
  AISettingsUpdate, AISettingsOut, AISettingsTestResult,
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
  me: (): Promise<AxiosResponse<{ id: string; email: string; name: string; auth_provider: string; role: string; created_at?: string }>> =>
    api.get('/auth/me'),
  changePassword: (data: { current_password: string; new_password: string }): Promise<AxiosResponse<AuthTokens>> =>
    api.post('/auth/change-password', data),
  deleteAccount: (data: { email_confirmation: string; password: string }): Promise<AxiosResponse<void>> =>
    api.delete('/auth/me', { data }),
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
  upload: (projectId: string, file: File): Promise<AxiosResponse<{ message: string; years: number[]; detected_revenue_streams: string[] }>> => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/projects/${projectId}/upload/historical`, form)
  },
  batchUpload: (projectId: string, files: File[], entityId?: string): Promise<AxiosResponse<any>> => {
    const form = new FormData()
    files.forEach(f => form.append('files', f))
    if (entityId) form.append('entity_id', entityId)
    return api.post(`/projects/${projectId}/documents/batch`, form)
  },
  getDocuments: (projectId: string): Promise<AxiosResponse<import('../types/api').UploadedDocument[]>> =>
    api.get(`/projects/${projectId}/documents`),
  toggleDocument: (projectId: string, docId: string, is_ignored: boolean): Promise<AxiosResponse<{ message: string; is_ignored: boolean }>> =>
    api.patch(`/projects/${projectId}/documents/${docId}/toggle`, { is_ignored }),
  deleteDocument: (projectId: string, docId: string): Promise<AxiosResponse<{ message: string }>> =>
    api.delete(`/projects/${projectId}/documents/${docId}`),
  analyzeDocument: (projectId: string, docId: string): Promise<AxiosResponse<{ message: string; ai_analysis: any; missing_inputs: string[] }>> =>
    api.post(`/projects/${projectId}/documents/${docId}/analyze`),
  saveJSON: (projectId: string, data: { parsed: any; years: number[]; entity_id?: string }): Promise<AxiosResponse<{ message: string }>> =>
    api.post(`/projects/${projectId}/save-json`, data),
  getData: (projectId: string): Promise<AxiosResponse<HistoricalResponse>> =>
    api.get(`/projects/${projectId}/historical`),
  getEntityHistorical: (entityId: string): Promise<AxiosResponse<HistoricalResponse>> =>
    api.get(`/entities/${entityId}/historical`),
}

// Assumptions
// scenarioId is forwarded as a query param to read/write the right scenario's
// assumption bucket. Pass null/undefined to operate on the Base scenario.
const scenarioParams = (scenarioId?: string | null) =>
  scenarioId ? { params: { scenario_id: scenarioId } } : undefined

export const assumptionsApi = {
  getAll: (projectId: string, scenarioId?: string | null): Promise<AxiosResponse<AllAssumptions>> =>
    api.get(`/projects/${projectId}/assumptions`, scenarioParams(scenarioId)),
  getModule: (projectId: string, module: string, scenarioId?: string | null): Promise<AxiosResponse<AssumptionItem[]>> =>
    api.get(`/projects/${projectId}/assumptions/${module}`, scenarioParams(scenarioId)),
  saveModule: (projectId: string, module: string, data: AssumptionItem[], scenarioId?: string | null): Promise<AxiosResponse<{ message: string }>> =>
    api.put(`/projects/${projectId}/assumptions/${module}`, data, scenarioParams(scenarioId)),
  getModuleStatus: (projectId: string, scenarioId?: string | null): Promise<AxiosResponse<ModuleStatus[]>> =>
    api.get(`/projects/${projectId}/modules/status`, scenarioParams(scenarioId)),
  autoSeed: (projectId: string): Promise<AxiosResponse<{ message: string }>> =>
    api.post(`/projects/${projectId}/assumptions/auto-seed`),
  aiHypothesis: (projectId: string): Promise<AxiosResponse<{
    sector: string
    items_persisted: number
    items: { module: string; line_item: string; rationale: string }[]
  }>> =>
    api.post(`/projects/${projectId}/assumptions/ai-hypothesis`),
}

// Templates
export const templatesApi = {
  downloadModule: (projectId: string, module: string): Promise<AxiosResponse<Blob>> =>
    api.get(`/projects/${projectId}/template/${module}`, { responseType: 'blob' }),
}

// Projections
//
// Async note: when project.projection_years > 10 the backend returns 202 with
// a Celery task_id instead of running synchronously. `run` transparently polls
// `checkStatus` until completion so callers can await a single promise without
// caring whether the run was sync or async. Polls every 2s, times out at 5min.
const ASYNC_POLL_INTERVAL_MS = 2000
const ASYNC_POLL_TIMEOUT_MS = 5 * 60 * 1000

export const projectionsApi = {
  get: (projectId: string): Promise<AxiosResponse<ProjectionsResponse>> =>
    api.get(`/projects/${projectId}/projections`),
  run: async (projectId: string): Promise<AxiosResponse<RunProjectionResponse | { status: string }>> => {
    const res = await api.post<RunProjectionResponse | { task_id: string; status: string }>(
      `/projects/${projectId}/projections/run`
    )
    if (res.status !== 202 || !(res.data as any)?.task_id) {
      return res as AxiosResponse<RunProjectionResponse>
    }
    const taskId = (res.data as any).task_id as string
    const startedAt = Date.now()
    while (true) {
      await new Promise(r => setTimeout(r, ASYNC_POLL_INTERVAL_MS))
      const status = await api.get<{ status: string }>(`/projects/${projectId}/run/status/${taskId}`)
      if (status.data.status === 'completed') return status
      if (Date.now() - startedAt > ASYNC_POLL_TIMEOUT_MS) {
        throw new Error('Projection timed out after 5 minutes. Check Celery worker logs.')
      }
    }
  },
  checkStatus: (projectId: string, taskId: string): Promise<AxiosResponse<{ status: string }>> =>
    api.get(`/projects/${projectId}/run/status/${taskId}`),
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

// Sector catalog (drives the project setup picker + sector-aware auto-seed)
export interface SectorOption {
  id: string
  label: string
  description: string
  key_kpis: string[]
}
export interface SectorGroup {
  group: string
  sectors: SectorOption[]
}
export const sectorsApi = {
  list: (): Promise<AxiosResponse<SectorGroup[]>> =>
    api.get(`/projects/_meta/sectors`),
}

// Block 1 — Scenarios
export const scenariosApi = {
  list: (projectId: string) => api.get(`/projects/${projectId}/scenarios`),
  create: (projectId: string, data: any) => api.post(`/projects/${projectId}/scenarios`, data),
  delete: (projectId: string, scenarioId: string) => api.delete(`/projects/${projectId}/scenarios/${scenarioId}`),
  run: (projectId: string, scenarioId: string) => api.post(`/projects/${projectId}/scenarios/${scenarioId}/run`),
  compare: (projectId: string, scenarioIds: string[]) =>
    api.get(`/projects/${projectId}/scenarios/compare`, { params: { ids: scenarioIds.join(',') } }),
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

// Revenue Streams — multi-line revenue configuration
export const revenueStreamsApi = {
  list: (projectId: string): Promise<AxiosResponse<Array<{ id: string | null; stream_name: string; display_order: number; projection_method: string }>>> =>
    api.get(`/projects/${projectId}/revenue-streams`),
  save: (projectId: string, streams: Array<{ stream_name: string; display_order: number; projection_method?: string }>): Promise<AxiosResponse<{ message: string; streams: string[] }>> =>
    api.put(`/projects/${projectId}/revenue-streams`, streams),
  detect: (projectId: string): Promise<AxiosResponse<{ detected_streams: Array<{ stream_name: string; is_standard: boolean; historical?: Record<string, string> }>; has_sub_lines: boolean; historical_preview?: Record<string, string> }>> =>
    api.post(`/projects/${projectId}/revenue-streams/detect`),
}

// Phase 3 — Consolidated View + Intercompany Eliminations
export const consolidatedApi = {
  getProjections: (projectId: string, scenarioId?: string): Promise<AxiosResponse<ConsolidatedResponse>> =>
    api.get(`/projects/${projectId}/consolidated/projections`, { params: scenarioId ? { scenario_id: scenarioId } : {} }),
  getHistorical: (projectId: string): Promise<AxiosResponse<ConsolidatedResponse>> =>
    api.get(`/projects/${projectId}/consolidated/historical`),
  listEliminations: (projectId: string): Promise<AxiosResponse<IntercompanyElimination[]>> =>
    api.get(`/projects/${projectId}/eliminations`),
  createElimination: (projectId: string, data: EliminationCreate): Promise<AxiosResponse<{ id: string; message: string }>> =>
    api.post(`/projects/${projectId}/eliminations`, data),
  updateElimination: (projectId: string, elimId: string, data: Partial<EliminationCreate>): Promise<AxiosResponse<{ id: string; message: string }>> =>
    api.put(`/projects/${projectId}/eliminations/${elimId}`, data),
  deleteElimination: (projectId: string, elimId: string): Promise<AxiosResponse<void>> =>
    api.delete(`/projects/${projectId}/eliminations/${elimId}`),
}

// Block 6 — External Curves / Indices
export const curvesApi = {
  get: (projectId: string) => api.get(`/projects/${projectId}/curves`),
  save: (projectId: string, data: Record<string, { is_percentage: boolean, values: Record<string, number> }>) => 
    api.put(`/projects/${projectId}/curves`, data),
}

// Admin — usage stats and user management
export interface AdminStats {
  users_total: number
  users_active: number
  users_new_30d: number
  users_admins: number
  users_master_admins: number
  projects_total: number
  projects_by_status: Record<string, number>
  projects_new_30d: number
  entities_total: number
  entities_by_type: Record<string, number>
  historical_rows: number
  uploads_total: number
  uploads_validated: number
  uploads_rejected: number
  uploads_pending: number
  timestamp: string
}

export interface AdminUser {
  id: string
  email: string
  name: string
  role: 'user' | 'admin' | 'master_admin'
  auth_provider: string
  created_at: string
  deleted_at: string | null
  project_count: number
}

export interface AdminUserListResponse {
  items: AdminUser[]
  total: number
  page: number
  page_size: number
}

export const adminApi = {
  stats: (): Promise<AxiosResponse<AdminStats>> => api.get('/admin/stats'),
  listUsers: (params: { q?: string; role?: string; include_deleted?: boolean; page?: number; page_size?: number } = {}):
    Promise<AxiosResponse<AdminUserListResponse>> =>
    api.get('/admin/users', { params }),
  updateUser: (userId: string, data: { role?: 'user' | 'admin' | 'master_admin'; deactivate?: boolean }):
    Promise<AxiosResponse<AdminUser>> =>
    api.patch(`/admin/users/${userId}`, data),
}

// AI Settings — user API keys for AI ingestion
export const aiSettingsApi = {
  get: (): Promise<AxiosResponse<AISettingsOut>> =>
    api.get('/me/ai-settings'),
  save: (data: AISettingsUpdate): Promise<AxiosResponse<AISettingsOut>> =>
    api.put('/me/ai-settings', data),
  delete: (): Promise<AxiosResponse<void>> =>
    api.delete('/me/ai-settings'),
  test: (): Promise<AxiosResponse<AISettingsTestResult>> =>
    api.post('/me/ai-settings/test'),
}

export default api
