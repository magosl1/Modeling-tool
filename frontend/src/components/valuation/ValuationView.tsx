import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useMutation, useQuery } from '@tanstack/react-query'
import { valuationApi } from '../../services/api'
import { useFormatNumber } from '../../utils/formatters'
import toast from 'react-hot-toast'

interface Props { projectId: string }

interface ValuationForm {
  wacc: number
  terminal_growth_rate: number
  exit_multiple: number | null
  discounting_convention: 'end_of_year' | 'mid_year'
  shares_outstanding: number | null
  tv_method: 'gordon_growth' | 'exit_multiple'
}

export default function ValuationView({ projectId }: Props) {
  const fmt = useFormatNumber()
  const { register, handleSubmit, watch } = useForm<ValuationForm>({
    defaultValues: {
      wacc: 10,
      terminal_growth_rate: 2.5,
      exit_multiple: null,
      discounting_convention: 'end_of_year',
      shares_outstanding: null,
      tv_method: 'gordon_growth',
    },
  })
  const tvMethod = watch('tv_method')

  const { data: existing } = useQuery({
    queryKey: ['valuation', projectId],
    queryFn: () => valuationApi.get(projectId).then(r => r.data),
    retry: false,
  })

  const [result, setResult] = useState<any>(existing || null)

  const runMutation = useMutation({
    mutationFn: (data: any) => valuationApi.run(projectId, data),
    onSuccess: (res) => {
      setResult(res.data)
      toast.success('DCF valuation complete!')
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || 'Valuation failed'),
  })

  const onSubmit = (data: ValuationForm) => {
    runMutation.mutate({
      wacc: data.wacc,
      terminal_growth_rate: data.terminal_growth_rate,
      exit_multiple: tvMethod === 'exit_multiple' ? data.exit_multiple : null,
      discounting_convention: data.discounting_convention,
      shares_outstanding: data.shares_outstanding || null,
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">DCF Valuation</h2>
        <p className="text-sm text-gray-500 mt-1">Enter WACC and terminal value assumptions to compute enterprise and equity value.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Panel */}
        <div className="card">
          <h3 className="font-medium text-gray-900 mb-4">Valuation Inputs</h3>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="label">WACC (%)</label>
              <input type="number" step="0.1" className="input" {...register('wacc', { valueAsNumber: true })} />
            </div>

            <div>
              <label className="label">Terminal Value Method</label>
              <select className="input" {...register('tv_method')}>
                <option value="gordon_growth">Gordon Growth Model</option>
                <option value="exit_multiple">Exit Multiple (EV/EBITDA)</option>
              </select>
            </div>

            {tvMethod === 'gordon_growth' && (
              <div>
                <label className="label">Terminal Growth Rate (%)</label>
                <input type="number" step="0.1" className="input" {...register('terminal_growth_rate', { valueAsNumber: true })} />
              </div>
            )}

            {tvMethod === 'exit_multiple' && (
              <div>
                <label className="label">Exit Multiple (EV/EBITDA)</label>
                <input type="number" step="0.1" className="input" {...register('exit_multiple', { valueAsNumber: true })} placeholder="e.g. 10" />
              </div>
            )}

            <div>
              <label className="label">Discounting Convention</label>
              <select className="input" {...register('discounting_convention')}>
                <option value="end_of_year">End of Year</option>
                <option value="mid_year">Mid-Year</option>
              </select>
            </div>

            <div>
              <label className="label">Shares Outstanding (optional)</label>
              <input type="number" className="input" {...register('shares_outstanding', { valueAsNumber: true })} placeholder="For per-share value" />
            </div>

            <button type="submit" disabled={runMutation.isPending} className="btn-primary w-full">
              {runMutation.isPending ? 'Computing...' : '▶ Run DCF Valuation'}
            </button>
          </form>
        </div>

        {/* Output Panel */}
        {result && (
          <div className="card">
            <h3 className="font-medium text-gray-900 mb-4">Valuation Output</h3>
            <div className="space-y-3">
              {[
                { label: 'PV of FCFFs', value: result.pv_fcffs },
                { label: 'Terminal Value', value: result.terminal_value },
                { label: 'PV of Terminal Value', value: result.pv_terminal_value },
                { label: 'Enterprise Value', value: result.enterprise_value, highlight: true },
                { label: 'Net Debt', value: result.net_debt },
                { label: 'Equity Value', value: result.equity_value, highlight: true },
                ...(result.value_per_share ? [{ label: 'Value per Share', value: result.value_per_share, highlight: true }] : []),
              ].map(item => (
                <div key={item.label} className={`flex justify-between py-2 ${item.highlight ? 'border-t border-gray-200 font-semibold' : ''}`}>
                  <span className={item.highlight ? 'text-gray-900' : 'text-gray-600'}>{item.label}</span>
                  <span className={item.highlight ? 'text-primary-700 text-lg' : 'text-gray-900 tabular-nums'}>
                    {fmt(item.value)}
                  </span>
                </div>
              ))}
            </div>

            <p className="text-xs text-gray-400 mt-4">
              Method: {result.method_used === 'gordon_growth' ? 'Gordon Growth Model' : 'Exit Multiple'}
              {' · '}Note: Interest calculated on beginning-of-period balances (no circularity).
            </p>
          </div>
        )}
      </div>

      {/* FCFF by Year */}
      {result?.fcff_by_year && (
        <div className="card">
          <h3 className="font-medium text-gray-900 mb-4">Free Cash Flow to Firm (FCFF)</h3>
          <div className="overflow-x-auto">
            <table className="text-sm w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  {Object.keys(result.fcff_by_year).map(y => (
                    <th key={y} className="text-right py-2 px-4 text-blue-600 font-medium">{y}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  {Object.values(result.fcff_by_year).map((v: any, i: number) => (
                    <td key={i} className="text-right py-2 px-4 tabular-nums">{fmt(v)}</td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Sensitivity Table */}
      {result?.sensitivity_table && (
        <div className="card">
          <h3 className="font-medium text-gray-900 mb-1">Sensitivity Analysis</h3>
          <p className="text-xs text-gray-500 mb-4">WACC (rows) × Terminal Growth Rate (cols) — showing Equity Value per Share (or Equity Value if no shares entered)</p>
          <div className="overflow-x-auto">
            <table className="text-xs w-full">
              <thead>
                <tr className="bg-gray-50">
                  <th className="py-2 px-3 text-left font-medium">WACC \ g</th>
                  {Object.keys(Object.values(result.sensitivity_table)[0] as any).map(g => (
                    <th key={g} className="py-2 px-3 text-right font-medium text-blue-600">{g}%</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(result.sensitivity_table).map(([wacc, gVals]: [string, any]) => (
                  <tr key={wacc} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 px-3 font-medium text-gray-700">{wacc}%</td>
                    {Object.values(gVals).map((v: any, i: number) => (
                      <td key={i} className="py-2 px-3 text-right tabular-nums">{fmt(v)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
