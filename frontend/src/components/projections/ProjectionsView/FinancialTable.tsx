import React from 'react'

import { useFormatNumber } from '../../../utils/formatters'
import { COST_LINES, SUBTOTALS, fmtVal, growth } from './constants'

function SubRow({
  label,
  values,
  years,
  projectedYears,
}: {
  label: string
  values: Record<number, string>
  years: number[]
  projectedYears: Set<number>
}) {
  return (
    <tr className="border-b border-gray-100">
      <td className="py-1 pr-4 text-xs text-gray-400 pl-4 italic sticky left-0 z-10 bg-white shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)] whitespace-nowrap">
        {label}
      </td>
      {years.map(y => (
        <td
          key={y}
          className={`py-1 px-3 text-right text-xs tabular-nums italic ${
            projectedYears.has(y) ? 'text-blue-400 bg-blue-50/30' : 'text-gray-400'
          }`}
        >
          {values[y] ?? '—'}
        </td>
      ))}
    </tr>
  )
}

export default function FinancialTable({
  title,
  items,
  data,
  years,
  projectedYears,
  pnlData,
}: {
  title: string
  items: string[]
  data: Record<string, Record<string, string>>
  years: number[]
  projectedYears: Set<number>
  pnlData?: Record<string, Record<string, string>>
}) {
  const fmt = useFormatNumber()
  const isPNL = title === 'P&L'

  const revenueGrowth: Record<number, string> = {}
  const ebitdaMargin: Record<number, string> = {}
  if (isPNL && pnlData) {
    years.forEach((y, idx) => {
      revenueGrowth[y] =
        idx === 0 ? '—' : growth(pnlData['Revenue']?.[y], pnlData['Revenue']?.[years[idx - 1]])
      const ebitda = parseFloat(String(pnlData['EBITDA']?.[y] ?? '0'))
      const rev = parseFloat(String(pnlData['Revenue']?.[y] ?? '0'))
      ebitdaMargin[y] = rev ? ((ebitda / rev) * 100).toFixed(1) + '%' : '—'
    })
  }

  return (
    <div className="mb-8">
      <h3 className="font-semibold text-gray-800 mb-3">{title}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 pr-4 font-medium text-gray-600 w-64 sticky left-0 z-20 bg-white shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)]">
                Line Item
              </th>
              {years.map(y => (
                <th
                  key={y}
                  className={`text-right py-2 px-3 font-medium min-w-24 ${
                    projectedYears.has(y) ? 'text-blue-600 bg-blue-50' : 'text-gray-600'
                  }`}
                >
                  {y}
                  {projectedYears.has(y) ? 'P' : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map(item => {
              const isSubtotal = SUBTOTALS.has(item)
              const isCost = COST_LINES.has(item)
              return (
                <React.Fragment key={item}>
                  <tr className={`border-b border-gray-100 ${isSubtotal ? 'font-semibold bg-gray-50' : ''}`}>
                    <td
                      className={`py-1.5 pr-4 text-gray-700 sticky left-0 z-10 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)] whitespace-nowrap ${
                        isSubtotal ? 'bg-gray-50' : 'bg-white'
                      }`}
                    >
                      {item}
                    </td>
                    {years.map(y => {
                      const raw = data[item]?.[y]
                      let displayRaw = raw
                      if (isCost && raw !== undefined && raw !== null && raw !== '') {
                        const n = parseFloat(String(raw))
                        if (!isNaN(n) && n > 0) displayRaw = String(-n)
                      }
                      const { text, negative } = fmtVal(displayRaw, fmt)
                      return (
                        <td
                          key={y}
                          className={`py-1.5 px-3 text-right tabular-nums ${
                            negative
                              ? 'text-red-600'
                              : projectedYears.has(y)
                                ? 'text-blue-900'
                                : 'text-gray-900'
                          } ${projectedYears.has(y) ? 'bg-blue-50/50' : ''}`}
                        >
                          {text}
                        </td>
                      )
                    })}
                  </tr>
                  {isPNL && item === 'Revenue' && (
                    <SubRow
                      label="↳ YoY Growth"
                      values={revenueGrowth}
                      years={years}
                      projectedYears={projectedYears}
                    />
                  )}
                  {isPNL && item === 'EBITDA' && (
                    <SubRow
                      label="↳ EBITDA Margin"
                      values={ebitdaMargin}
                      years={years}
                      projectedYears={projectedYears}
                    />
                  )}
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
