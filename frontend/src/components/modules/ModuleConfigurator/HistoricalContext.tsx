import { HistoricalData, LINE_ITEM_HIST_KEY } from './constants'

/** Show last 3 historical years for a given line item. */
export default function HistoricalContext({
  lineItem,
  statement,
  historicalData,
  fmt,
}: {
  lineItem: string
  statement: 'PNL' | 'BS' | 'CF'
  historicalData?: HistoricalData
  fmt: (v: any) => string
}) {
  if (!historicalData) return null
  const stmtData = historicalData[statement] || {}
  const histKey = LINE_ITEM_HIST_KEY[lineItem] || lineItem
  const yearVals = stmtData[histKey] || {}
  const years = Object.keys(yearVals).map(Number).sort().slice(-3)
  if (years.length === 0) return null

  return (
    <div className="flex items-center gap-3 flex-wrap mt-1 mb-2 px-2 py-1.5 bg-blue-50 rounded text-xs text-blue-700 border border-blue-100">
      <span className="font-medium text-blue-600">📊 Historical:</span>
      {years.map(y => (
        <span key={y} className="tabular-nums">
          <span className="text-blue-400">{y}: </span>
          <span className="font-medium">{fmt(yearVals[y.toString()])}</span>
        </span>
      ))}
      <span className="text-blue-400 italic ml-1">· Base = last year ({years[years.length - 1]})</span>
    </div>
  )
}
