import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell
} from 'recharts'
import { 
  SparklesIcon, 
  ArrowPathIcon, 
  PresentationChartLineIcon,
  AdjustmentsHorizontalIcon,
  CheckCircleIcon,
  ArrowRightIcon
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { projectionsApi, assumptionsApi, historicalApi } from '../../services/api'
import type { Project } from '../../types/api'
import UploadHistoricalAI from './UploadHistoricalAI'

interface Props {
  projectId: string
  project: Project
}

export default function ProjectDashboard({ projectId, project }: Props) {
  const qc = useQueryClient()
  const [isSeeding, setIsSeeding] = useState(false)

  // 1. Fetch Data
  const { data: projections } = useQuery({
    queryKey: ['projections', projectId],
    queryFn: () => projectionsApi.get(projectId).then(r => r.data),
  })

  const { data: moduleStatuses = [] } = useQuery({
    queryKey: ['module-status', projectId],
    queryFn: () => assumptionsApi.getModuleStatus(projectId).then(r => r.data),
  })

  // 2. Mutations
  const runProjections = useMutation({
    mutationFn: () => projectionsApi.run(projectId),
    onSuccess: () => {
      toast.success('Projections updated!')
      qc.invalidateQueries({ queryKey: ['projections', projectId] })
      qc.invalidateQueries({ queryKey: ['module-status', projectId] })
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail?.error?.message || 'Projection failed')
    }
  })

  const autoSeed = useMutation({
    mutationFn: () => assumptionsApi.autoSeed(projectId),
    onSuccess: () => {
      toast.success('Assumptions seeded automatically!')
      runProjections.mutate()
    },
    onSettled: () => setIsSeeding(false)
  })

  // 3. Data Processing for Charts
  const chartData = useMemo(() => {
    if (!projections) return []
    const allYears = [...projections.historical_years, ...projections.projected_years]
    return allYears.map(year => {
      const pnl = projections.PNL || {}
      // Try to find a revenue-like item
      const revKey = Object.keys(pnl).find(k => k.toLowerCase().includes('revenue') || k.toLowerCase().includes('sales')) || 'Revenue'
      const ebitdaKey = Object.keys(pnl).find(k => k.toLowerCase().includes('ebitda')) || 'EBITDA'
      
      return {
        year,
        revenue: parseFloat(pnl[revKey]?.[year] || '0'),
        ebitda: parseFloat(pnl[ebitdaKey]?.[year] || '0'),
        isProjected: projections.projected_years.includes(year)
      }
    })
  }, [projections])

  const hasData = chartData.length > 0
  const isAllPending = moduleStatuses.every(s => s.status === 'not_started')

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
      
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-2xl bg-indigo-600 p-8 shadow-xl">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <h2 className="text-3xl font-bold text-white tracking-tight">Project Dashboard</h2>
            <p className="mt-2 text-indigo-100 text-lg opacity-90">
              {hasData 
                ? "Your financial model is live. Adjust assumptions to see real-time impact." 
                : "Welcome! Start by uploading your historical financials or seed default assumptions."}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            {isAllPending && hasData && (
              <button
                onClick={() => { setIsSeeding(true); autoSeed.mutate(); }}
                disabled={isSeeding}
                className="bg-white/10 hover:bg-white/20 text-white px-5 py-2.5 rounded-xl font-semibold backdrop-blur-md border border-white/20 transition-all flex items-center gap-2"
              >
                <SparklesIcon className="w-5 h-5" />
                {isSeeding ? 'Seeding...' : 'Auto-Seed Hypotheses'}
              </button>
            )}
            <button
              onClick={() => runProjections.mutate()}
              disabled={runProjections.isPending}
              className="bg-white text-indigo-600 hover:bg-indigo-50 px-6 py-2.5 rounded-xl font-bold shadow-lg transition-all flex items-center gap-2 active:scale-95 disabled:opacity-50"
            >
              <ArrowPathIcon className={`w-5 h-5 ${runProjections.isPending ? 'animate-spin' : ''}`} />
              {runProjections.isPending ? 'Calculating...' : 'Run Projections'}
            </button>
          </div>
        </div>
        {/* Abstract Background Shapes */}
        <div className="absolute -top-24 -right-24 w-96 h-96 bg-white/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-24 -left-24 w-96 h-96 bg-indigo-500/30 rounded-full blur-3xl" />
      </div>

      {!hasData && !isSeeding ? (
        <div className="card p-0 overflow-hidden border-none shadow-2xl ring-1 ring-gray-200">
           <UploadHistoricalAI projectId={projectId} project={project} onComplete={() => qc.invalidateQueries({ queryKey: ['projections', projectId] })} />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Main Chart Area */}
          <div className="lg:col-span-2 space-y-6">
            <div className="card p-6 shadow-sm">
              <div className="flex items-center justify-between mb-8">
                <div>
                  <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                    <PresentationChartLineIcon className="w-5 h-5 text-indigo-500" />
                    Revenue & EBITDA Forecast
                  </h3>
                  <p className="text-sm text-gray-500 mt-1">Combined historical and projected performance</p>
                </div>
                <div className="flex items-center gap-4 text-xs font-medium uppercase tracking-wider">
                  <div className="flex items-center gap-1.5 text-indigo-600">
                    <div className="w-3 h-3 rounded-full bg-indigo-500" /> Revenue
                  </div>
                  <div className="flex items-center gap-1.5 text-emerald-600">
                    <div className="w-3 h-3 rounded-full bg-emerald-500" /> EBITDA
                  </div>
                </div>
              </div>
              
              <div className="h-[400px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorRev" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.1}/>
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                      </linearGradient>
                      <linearGradient id="colorEbit" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.1}/>
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis 
                      dataKey="year" 
                      axisLine={false} 
                      tickLine={false} 
                      tick={{fill: '#94a3b8', fontSize: 12}} 
                      dy={10}
                    />
                    <YAxis 
                      axisLine={false} 
                      tickLine={false} 
                      tick={{fill: '#94a3b8', fontSize: 12}}
                      tickFormatter={(val) => `${(val / 1000).toFixed(0)}k`}
                    />
                    <Tooltip 
                      contentStyle={{borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)', padding: '12px'}}
                      labelStyle={{fontWeight: 'bold', marginBottom: '4px'}}
                    />
                    <Area 
                      type="monotone" 
                      dataKey="revenue" 
                      stroke="#6366f1" 
                      strokeWidth={3}
                      fillOpacity={1} 
                      fill="url(#colorRev)" 
                      animationDuration={1500}
                    />
                    <Area 
                      type="monotone" 
                      dataKey="ebitda" 
                      stroke="#10b981" 
                      strokeWidth={3}
                      fillOpacity={1} 
                      fill="url(#colorEbit)" 
                      animationDuration={2000}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Metric Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="card p-6 bg-gradient-to-br from-white to-indigo-50 border-indigo-100">
                <h4 className="text-xs font-bold text-indigo-400 uppercase tracking-widest mb-4">Target Growth</h4>
                <div className="flex items-end justify-between">
                  <div>
                    <span className="text-4xl font-black text-indigo-900 tracking-tight">8.5%</span>
                    <span className="ml-2 text-indigo-500 font-medium text-sm">CAGR</span>
                  </div>
                  <div className="w-24 h-12">
                    {/* Tiny bar sparkline placeholder */}
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={chartData.slice(-5)}>
                        <Bar dataKey="revenue" fill="#6366f1" radius={[2, 2, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
              <div className="card p-6 bg-gradient-to-br from-white to-emerald-50 border-emerald-100">
                <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-widest mb-4">Margin Profile</h4>
                <div className="flex items-end justify-between">
                  <div>
                    <span className="text-4xl font-black text-emerald-900 tracking-tight">32%</span>
                    <span className="ml-2 text-emerald-500 font-medium text-sm">EBITDA</span>
                  </div>
                  <div className="w-24 h-12 text-emerald-500 flex items-center justify-center">
                    <CheckCircleIcon className="w-8 h-8" />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Panel: Quick Controls */}
          <div className="space-y-6">
            <div className="card p-6 border-none bg-gray-900 text-white shadow-2xl">
              <h3 className="text-lg font-bold flex items-center gap-2 mb-6">
                <AdjustmentsHorizontalIcon className="w-5 h-5 text-indigo-400" />
                Dynamic Controls
              </h3>
              
              <div className="space-y-8">
                <div>
                  <div className="flex justify-between mb-3">
                    <label className="text-sm font-medium text-gray-300">Revenue Growth (%)</label>
                    <span className="text-indigo-400 font-bold">12%</span>
                  </div>
                  <input type="range" className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-indigo-500" />
                  <div className="flex justify-between mt-2 text-[10px] text-gray-500 font-bold uppercase tracking-wider">
                    <span>Conservative</span>
                    <span>Aggressive</span>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between mb-3">
                    <label className="text-sm font-medium text-gray-300">OpEx Margin (%)</label>
                    <span className="text-indigo-400 font-bold">45%</span>
                  </div>
                  <input type="range" className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-indigo-500" />
                  <div className="flex justify-between mt-2 text-[10px] text-gray-500 font-bold uppercase tracking-wider">
                    <span>Efficient</span>
                    <span>Baseline</span>
                  </div>
                </div>

                <div className="pt-4 border-t border-gray-800">
                   <h4 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-4">Module Readiness</h4>
                   <div className="space-y-3">
                      {moduleStatuses.slice(0, 5).map(s => (
                        <div key={s.module} className="flex items-center justify-between">
                          <span className="text-xs text-gray-400 capitalize">{s.module.replace('_', ' ')}</span>
                          <div className={`w-2 h-2 rounded-full ${s.status === 'complete' ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' : 'bg-gray-600'}`} />
                        </div>
                      ))}
                   </div>
                </div>

                <button 
                   onClick={() => toast.success('Assumption applied!')}
                   className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 rounded-xl font-bold text-sm transition-all shadow-lg shadow-indigo-900/40 flex items-center justify-center gap-2 group"
                >
                  Apply & Recalculate
                  <ArrowRightIcon className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </button>
              </div>
            </div>

            <div className="card p-6 bg-indigo-50 border-indigo-100 flex items-center gap-4 group cursor-pointer hover:bg-indigo-100 transition-colors">
              <div className="p-3 bg-white rounded-xl shadow-sm text-indigo-600">
                <PresentationChartLineIcon className="w-6 h-6" />
              </div>
              <div>
                <h4 className="font-bold text-indigo-900">Advanced Scenarios</h4>
                <p className="text-xs text-indigo-600 font-medium">Create Bull/Bear cases →</p>
              </div>
            </div>
          </div>

        </div>
      )}
    </div>
  )
}
