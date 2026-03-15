import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { debtApi, projectionsApi } from '../../services/api'
import toast from 'react-hot-toast'

interface Props { projectId: string }

interface RevolverConfig {
  max_capacity: number
  interest_rate: number
  commitment_fee: number
  minimum_cash_balance: number
}

interface TermLoanTranche {
  id: string
  name: string
  principal: number
  interest_rate: number
  term_years: number
  amortization_type: 'bullet' | 'straight_line' | 'custom'
}

export default function DebtSchedulePanel({ projectId }: Props) {
  const qc = useQueryClient()
  const [activeTab, setActiveTab] = useState<'revolver' | 'tranches'>('tranches')

  // Revolver Form State
  const [revolver, setRevolver] = useState<RevolverConfig>({
    max_capacity: 0,
    interest_rate: 5.0,
    commitment_fee: 0.5,
    minimum_cash_balance: 1000000,
  })

  // Tranches Form State
  const [tranches, setTranches] = useState<TermLoanTranche[]>([])

  // Fetch Revolver
  const { isLoading: rLoading } = useQuery({
    queryKey: ['debt-revolver', projectId],
    queryFn: () => debtApi.getRevolver(projectId).then(r => r.data),
    meta: {
      onSuccess: (data: any) => {
        if (data) setRevolver(data)
      }
    }
  })

  // Fetch Tranches
  const { isLoading: tLoading } = useQuery({
    queryKey: ['debt-tranches', projectId],
    queryFn: () => debtApi.getTranches(projectId).then(r => r.data),
    meta: {
      onSuccess: (data: any[]) => {
        if (data) setTranches(data)
      }
    }
  })

  const runMutation = useMutation({
    mutationFn: () => projectionsApi.run(projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projections', projectId] }),
  })

  const saveRevolverM = useMutation({
    mutationFn: (data: RevolverConfig) => debtApi.saveRevolver(projectId, data),
    onSuccess: () => {
      toast.success('Revolver settings saved')
      runMutation.mutate()
    },
    onError: () => toast.error('Failed to save revolver')
  })

  const saveTranchesM = useMutation({
    mutationFn: (data: TermLoanTranche[]) => debtApi.saveTranches(projectId, data),
    onSuccess: () => {
      toast.success('Term loans saved')
      runMutation.mutate()
    },
    onError: () => toast.error('Failed to save term loans')
  })

  const addTranche = () => {
    setTranches([...tranches, {
      id: crypto.randomUUID(),
      name: `Term Loan ${tranches.length + 1}`,
      principal: 0,
      interest_rate: 6.0,
      term_years: 5,
      amortization_type: 'bullet'
    }])
  }

  const updateTranche = (id: string, updates: Partial<TermLoanTranche>) => {
    setTranches(prev => prev.map(t => t.id === id ? { ...t, ...updates } : t))
  }

  const removeTranche = (id: string) => {
    setTranches(prev => prev.filter(t => t.id !== id))
  }

  if (rLoading || tLoading) return <div className="card text-center p-8 text-gray-500">Loading debt schedule...</div>

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">Debt Schedule</h2>
        <p className="text-sm text-gray-500 mt-1">Configure Revolving Credit Facility and Term Loans.</p>
      </div>

      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setActiveTab('tranches')}
          className={`py-2 px-4 text-sm font-medium border-b-2 transition-colors ${activeTab === 'tranches' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
        >
          Term Loans
        </button>
        <button
          onClick={() => setActiveTab('revolver')}
          className={`py-2 px-4 text-sm font-medium border-b-2 transition-colors ${activeTab === 'revolver' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
        >
          Revolver (RCF)
        </button>
      </div>

      {activeTab === 'tranches' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={addTranche} className="btn-secondary text-sm">+ Add Term Loan</button>
          </div>
          
          {tranches.length === 0 ? (
            <div className="card text-center py-12 text-gray-500 bg-gray-50 border-dashed">
              No term loans defined. Add one to begin modeling structural debt.
            </div>
          ) : (
            <div className="space-y-4">
              {tranches.map(t => (
                <div key={t.id} className="card relative">
                  <button onClick={() => removeTranche(t.id)} className="absolute top-4 right-4 text-gray-400 hover:text-red-500">✕</button>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="col-span-2">
                      <label className="label">Tranche Name</label>
                      <input className="input" value={t.name} onChange={e => updateTranche(t.id, { name: e.target.value })} />
                    </div>
                    <div className="col-span-2">
                      <label className="label">Principal Amount</label>
                      <input type="number" className="input" value={t.principal} onChange={e => updateTranche(t.id, { principal: parseFloat(e.target.value) || 0 })} />
                    </div>
                    <div>
                      <label className="label">Interest Rate (%)</label>
                      <input type="number" step="0.1" className="input" value={t.interest_rate} onChange={e => updateTranche(t.id, { interest_rate: parseFloat(e.target.value) || 0 })} />
                    </div>
                    <div>
                      <label className="label">Term (Years)</label>
                      <input type="number" className="input" value={t.term_years} onChange={e => updateTranche(t.id, { term_years: parseInt(e.target.value) || 0 })} />
                    </div>
                    <div className="col-span-2">
                      <label className="label">Amortization Type</label>
                      <select className="input" value={t.amortization_type} onChange={e => updateTranche(t.id, { amortization_type: e.target.value as any })}>
                        <option value="bullet">Bullet (Paid at maturity)</option>
                        <option value="straight_line">Straight-Line</option>
                      </select>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="flex justify-end pt-4">
            <button
              onClick={() => saveTranchesM.mutate(tranches)}
              disabled={saveTranchesM.isPending}
              className="btn-primary"
            >
              {saveTranchesM.isPending ? 'Saving...' : 'Save Term Loans'}
            </button>
          </div>
        </div>
      )}

      {activeTab === 'revolver' && (
        <div className="card space-y-4">
          <p className="text-sm text-gray-600 mb-4">
            The revolving credit facility automatically draws to meet cash shortfalls below the minimum balance, and repays when excess cash is available.
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Max Capacity</label>
              <input type="number" className="input" value={revolver.max_capacity} onChange={e => setRevolver({ ...revolver, max_capacity: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label className="label">Minimum Cash Balance</label>
              <input type="number" className="input" value={revolver.minimum_cash_balance} onChange={e => setRevolver({ ...revolver, minimum_cash_balance: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label className="label">Draw Interest Rate (%)</label>
              <input type="number" step="0.1" className="input" value={revolver.interest_rate} onChange={e => setRevolver({ ...revolver, interest_rate: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label className="label">Commitment Fee (%)</label>
              <input type="number" step="0.1" className="input" value={revolver.commitment_fee} onChange={e => setRevolver({ ...revolver, commitment_fee: parseFloat(e.target.value) || 0 })} />
            </div>
          </div>
          <div className="flex justify-end pt-4">
            <button
              onClick={() => saveRevolverM.mutate(revolver)}
              disabled={saveRevolverM.isPending}
              className="btn-primary"
            >
              {saveRevolverM.isPending ? 'Saving...' : 'Save Revolver'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
