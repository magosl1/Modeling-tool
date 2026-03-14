import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { projectionsApi } from '../../services/api'

interface Props { projectId: string; module: string; }

const PNL_ITEMS = [
    'Revenue', 'Cost of Goods Sold', 'Gross Profit', 'SG&A', 'R&D', 'D&A',
    'Amortization of Intangibles', 'Other OpEx', 'EBIT', 'Interest Income',
    'Interest Expense', 'Other Non-Operating Income / (Expense)', 'EBT', 'Tax', 'Net Income',
]

const BS_ITEMS = [
    'PP&E Gross', 'Accumulated Depreciation', 'Net PP&E', 'Intangibles Gross',
    'Accumulated Amortization', 'Net Intangibles', 'Goodwill', 'Inventories',
    'Accounts Receivable', 'Prepaid Expenses & Other Current Assets',
    'Cash & Equivalents', 'Non-Operating Assets', 'Share Capital',
    'Retained Earnings', 'Other Equity (AOCI, Treasury Stock, etc.)',
    'Accounts Payable', 'Accrued Liabilities', 'Other Current Liabilities',
    'Short-Term Debt', 'Long-Term Debt'
]

const CF_ITEMS = [
    'Net Income', 'D&A Add-back', 'Amortization of Intangibles Add-back',
    'Changes in Working Capital', 'Operating Cash Flow', 'Capex',
    'Acquisitions / Disposals', 'Investing Cash Flow', 'Debt Issuance / Repayment',
    'Dividends Paid', 'Share Issuance / Buyback', 'Financing Cash Flow', 'Net Change in Cash',
]

const SUBTOTALS = new Set([
    'Gross Profit', 'EBIT', 'EBT', 'Net Income',
    'Operating Cash Flow', 'Investing Cash Flow', 'Financing Cash Flow', 'Net Change in Cash',
])

function fmt(val: string | undefined) {
    if (val === undefined || val === null) return '—'
    const n = parseFloat(val)
    if (isNaN(n)) return '—'
    return n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

function LiveFinancialTable({ items, data, years }: { items: string[]; data: Record<string, Record<string, string>>; years: number[] }) {
    return (
        <div className="overflow-auto border rounded-b-lg border-t-0 bg-white" style={{ maxHeight: '600px' }}>
            <table className="w-full text-xs">
                <thead className="sticky top-0 bg-gray-50 z-10 shadow-sm">
                    <tr className="border-b border-gray-200">
                        <th className="text-left py-2 pl-3 pr-2 font-medium text-gray-600 w-48 sticky left-0 bg-gray-50 z-20">Line Item</th>
                        {years.map(y => (
                            <th key={y} className="text-right py-2 px-2 font-medium text-blue-600 min-w-[70px]">{y}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {items.map(item => {
                        const isSubtotal = SUBTOTALS.has(item)
                        return (
                            <tr
                                key={item}
                                className={`border-b border-gray-100 ${isSubtotal ? 'font-semibold bg-blue-50/30' : 'hover:bg-gray-50'}`}
                            >
                                <td className="py-1.5 pl-3 pr-2 text-gray-700 sticky left-0 bg-white z-10 w-48 whitespace-nowrap overflow-hidden text-ellipsis shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)]" title={item}>
                                    {item}
                                </td>
                                {years.map(y => (
                                    <td key={y} className="py-1.5 px-2 text-right text-gray-900 tabular-nums">
                                        {fmt(data[item]?.[y])}
                                    </td>
                                ))}
                            </tr>
                        )
                    })}
                </tbody>
            </table>
        </div>
    )
}

export default function LiveProjectionsView({ projectId, module }: Props) {
    const [activeTab, setActiveTab] = useState<'PNL' | 'BS' | 'CF'>('PNL')

    const { data: projections, isFetching } = useQuery({
        queryKey: ['projections', projectId],
        queryFn: () => projectionsApi.get(projectId).then(r => r.data),
        // Fast refetch logic to ensure it stays hot, or reliances on queryClient invalidation
    })

    const hasProjections = projections && Object.keys(projections.PNL || {}).length > 0
    const years = hasProjections
        ? [...new Set(Object.values(projections.PNL as Record<string, Record<string, string>>).flatMap(v => Object.keys(v)).map(Number))].sort()
        : []

    const TABS = [
        { key: 'PNL', label: 'P&L', items: PNL_ITEMS },
        { key: 'BS', label: 'Balance Sheet', items: BS_ITEMS },
        { key: 'CF', label: 'Cash Flow', items: CF_ITEMS },
    ] as const

    return (
        <div className="flex flex-col h-full bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="p-4 border-b border-gray-200 bg-gray-50 flex items-center justify-between shrink-0">
                <div>
                    <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                        Live Model Preview
                        {isFetching && <span className="flex h-2 w-2 relative">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                        </span>}
                    </h2>
                    <p className="text-xs text-gray-500 mt-1">Updates instantly when you save assumptions</p>
                </div>
            </div>

            {!hasProjections ? (
                <div className="p-8 text-center text-gray-400 text-sm italic flex-1 flex flex-col justify-center">
                    Save an assumption to view live projection calculations. No projection data exists yet.
                </div>
            ) : (
                <div className="flex-1 flex flex-col min-h-0">
                    <div className="flex bg-white px-2 pt-2 border-b border-gray-200 shrink-0">
                        {TABS.map(tab => (
                            <button
                                key={tab.key}
                                onClick={() => setActiveTab(tab.key)}
                                className={`px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${activeTab === tab.key
                                        ? 'border-primary-600 text-primary-600'
                                        : 'border-transparent text-gray-500 hover:text-gray-700'
                                    }`}
                            >
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    <div className="flex-1 overflow-hidden relative">
                        {TABS.filter(t => t.key === activeTab).map(tab => (
                            <LiveFinancialTable
                                key={tab.key}
                                items={tab.items}
                                data={projections[tab.key] || {}}
                                years={years}
                            />
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}
