import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { useMutation, useQuery } from '@tanstack/react-query'
import { valuationApi } from '../../services/api'
import type { ValuationResult } from '../../types/api'
import { useFormatNumber } from '../../utils/formatters'
import MonteCarloView from './MonteCarloView'
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
  const [valTab, setValTab] = useState<'dcf' | 'mc'>('dcf')
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

  const [result, setResult] = useState<ValuationResult | null>(null)

  useEffect(() => {
    if (existing && !result) setResult(existing)
  }, [existing])

  const runMutation = useMutation({
    mutationFn: (data: ValuationForm) => valuationApi.run(projectId, {
      wacc: data.wacc,
      terminal_growth_rate: data.terminal_growth_rate,
      exit_multiple: data.tv_method === 'exit_multiple' ? data.exit_multiple : null,
      discounting_convention: data.discounting_convention,
      shares_outstanding: data.shares_outstanding || null,
    }),
    onSuccess: (res) => {
      setResult(res.data)
      toast.success('DCF valuation complete!')
    },
    onError: (err: unknown) => {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      toast.error(axiosErr.response?.data?.detail || 'Valuation failed')
    },
  })

  const onSubmit = (data: ValuationForm) => {
    runMutation.mutate(data)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Valuation</h2>
          <p className="text-sm text-gray-500 mt-1">DCF valuation and probabilistic simulation.</p>
        </div>
        <div className="ml-auto flex gap-1 border border-gray-200 rounded-lg overflow-hidden">
          <button
            onClick={() => setValTab('dcf')}
            className={`px-3 py-1.5 text-sm font-medium transition-colors ${valTab === 'dcf' ? 'bg-primary-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
          >DCF</button>
          <button
            onClick={() => setValTab('mc')}
            className={`px-3 py-1.5 text-sm font-medium transition-colors ${valTab === 'mc' ? 'bg-primary-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
          >🎲 Monte Carlo</button>
        </div>
      </div>

      {valTab === 'mc' && <MonteCarloView projectId={projectId} />}

      {valTab === 'dcf' && <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
      </div>}

      {valTab === 'dcf' && result?.fcff_build_up && (
        <div className="card">
          <h3 className="font-medium text-gray-900 mb-4">Free Cash Flow to Firm (FCFF) Build-up</h3>
          <div className="overflow-x-auto">
            <table className="text-sm w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 px-4 font-medium text-gray-500">Line Item</th>
                  {Object.keys(result.fcff_build_up).map(y => (
                    <th key={y} className="text-right py-2 px-4 text-blue-600 font-medium">{y}</th>
                  ))}
                  {result.normalized_terminal_year && (
                    <th className="text-right py-2 px-4 text-green-600 font-medium whitespace-nowrap">
                      Terminal ({result.normalized_terminal_year})
                    </th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {['EBIT', 'Taxes', 'NOPAT', 'D&A & Amort', 'Less: Changes in WC', 'Less: Capex', 'FCFF'].map((row) => (
                  <tr key={row} className={row === 'FCFF' ? 'font-semibold bg-gray-50' : ''}>
                    <td className="py-2 px-4 font-medium text-gray-700 whitespace-nowrap">{row}</td>
                    {Object.values(result.fcff_build_up).map((yearData: any, i: number) => (
                      <td key={i} className={`text-right py-2 px-4 tabular-nums ${row === 'FCFF' ? 'text-blue-700' : ''}`}>
                        {fmt(yearData[row])}
                      </td>
                    ))}
                    {result.terminal_fcff_build_up && (
                      <td className={`text-right py-2 px-4 tabular-nums ${row === 'FCFF' ? 'text-green-700 font-bold' : 'text-gray-600'}`}>
                        {fmt(result.terminal_fcff_build_up[row])}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {valTab === 'dcf' && result?.implied_multiples && (
        <div className="card">
          <h3 className="font-medium text-gray-900 mb-4">Implied Multiples</h3>
          <div className="overflow-x-auto">
            <table className="text-sm w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 px-4 font-medium text-gray-500">Multiple</th>
                  {Object.keys(result.implied_multiples).map(y => (
                    <th key={y} className="text-right py-2 px-4 text-gray-600 font-medium">{y}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {['EV / EBITDA', 'EV / Revenue', 'P / E'].map(mult => (
                  <tr key={mult}>
                    <td className="py-2 px-4 font-medium text-gray-700 whitespace-nowrap">{mult}</td>
                    {Object.values(result.implied_multiples).map((yearData: any, i: number) => (
                      <td key={i} className="text-right py-2 px-4 tabular-nums">
                        {yearData[mult] ? `${fmt(yearData[mult])}x` : 'N/A'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {valTab === 'dcf' && result?.sensitivity_table && (
        <div className="card">
          <h3 className="font-medium text-gray-900 mb-1">Sensitivity Analysis</h3>
          <p className="text-xs text-gray-500 mb-4">WACC (rows) × Terminal Growth Rate (cols) — showing Equity Value per Share (or Equity Value if no shares entered)</p>
          <div className="overflow-x-auto border border-gray-200 rounded-lg">
            <table className="text-sm w-full">
              <thead>
                <tr className="bg-gray-100 border-b border-gray-200">
                  <th className="py-2.5 px-3 text-center font-semibold text-gray-700 border-r border-gray-200">WACC \ g</th>
                  {Object.keys((Object.values(result.sensitivity_table)[0] as Record<string, unknown>) || {}).map(g => (
                    <th key={g} className="py-2.5 px-3 text-center font-medium text-gray-700">{g}%</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(result.sensitivity_table).map(([wacc, gVals]: [string, any]) => (
                  <tr key={wacc} className="border-b border-gray-100 last:border-0 hover:bg-gray-50/50">
                    <td className="py-2.5 px-3 font-semibold text-gray-700 text-center border-r border-gray-200 bg-gray-50">{wacc}%</td>
                    {Object.values(gVals).map((v: any, i: number) => (
                      <td key={i} className="py-2.5 px-3 text-center tabular-nums text-gray-800">
                        {fmt(v)}
                      </td>
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
