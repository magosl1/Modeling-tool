import { useFormatNumber } from '../../../utils/formatters'

/** Net Debt, Net Debt / Equity, Net Debt / EBITDA — shown under the BS tab. */
export default function KeyMetricsStrip({
  data,
  years,
  projectedYears,
  pnlData,
}: {
  data: Record<string, Record<string, string>>
  years: number[]
  projectedYears: Set<number>
  pnlData?: Record<string, Record<string, string>>
}) {
  const fmt = useFormatNumber()
  const metrics = years.map(y => {
    const stDebt = parseFloat(String(data['Short-Term Debt']?.[y] ?? '0'))
    const ltDebt = parseFloat(String(data['Long-Term Debt']?.[y] ?? '0'))
    const cash = parseFloat(String(data['Cash & Equivalents']?.[y] ?? '0'))
    const sc = parseFloat(String(data['Share Capital']?.[y] ?? '0'))
    const re = parseFloat(String(data['Retained Earnings']?.[y] ?? '0'))
    const oe = parseFloat(String(data['Other Equity (AOCI, Treasury Stock, etc.)']?.[y] ?? '0'))
    const netDebt = stDebt + ltDebt - cash
    const equity = sc + re + oe
    const ebitda = parseFloat(String(pnlData?.['EBITDA']?.[y] ?? '0'))
    return { y, netDebt, equity, ebitda }
  })

  const rows = [
    {
      label: 'Net Debt',
      values: metrics.map(m => ({ y: m.y, v: m.netDebt })),
    },
    {
      label: 'Net Debt / Equity',
      values: metrics.map(m => ({ y: m.y, v: m.equity ? m.netDebt / m.equity : NaN })),
    },
    {
      label: 'Net Debt / EBITDA',
      values: metrics.map(m => ({ y: m.y, v: m.ebitda ? m.netDebt / m.ebitda : NaN })),
    },
  ]

  return (
    <div className="mt-4 border-t border-gray-200 pt-4">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Key Metrics</p>
      <table className="w-full text-xs">
        <tbody>
          {rows.map(row => (
            <tr key={row.label} className="border-b border-gray-100">
              <td className="py-1 pr-4 font-medium text-gray-600 w-64 sticky left-0 z-10 bg-white shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)] whitespace-nowrap">
                {row.label}
              </td>
              {row.values.map(({ y, v }) => {
                const isRatio = row.label.includes('/')
                const text = isNaN(v)
                  ? '—'
                  : isRatio
                    ? v.toFixed(2) + 'x'
                    : v < 0
                      ? `(${fmt(Math.abs(v))})`
                      : fmt(v)
                const neg = v < 0
                return (
                  <td
                    key={y}
                    className={`py-1 px-3 text-right tabular-nums min-w-24 ${
                      neg ? 'text-red-600' : 'text-gray-700'
                    } ${projectedYears.has(y) ? 'bg-blue-50/30' : ''}`}
                  >
                    {text}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
