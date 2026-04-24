/**
 * Row ordering + classification used across the projections tables.
 * Pure data with no React dependency.
 */

export const PNL_ITEMS = [
  'Revenue', 'Cost of Goods Sold', 'Gross Profit', 'SG&A', 'R&D', 'D&A',
  'Amortization of Intangibles', 'Other OpEx', 'EBIT', 'EBITDA', 'Interest Income',
  'Interest Expense', 'Other Non-Operating Income / (Expense)', 'EBT', 'Tax', 'Net Income',
]

export const BS_ITEMS = [
  'PP&E Gross', 'Accumulated Depreciation', 'Net PP&E', 'Intangibles Gross',
  'Accumulated Amortization', 'Net Intangibles', 'Goodwill', 'Inventories',
  'Accounts Receivable', 'Prepaid Expenses & Other Current Assets', 'Accounts Payable',
  'Accrued Liabilities', 'Other Current Liabilities', 'Cash & Equivalents',
  'Non-Operating Assets', 'Short-Term Debt', 'Long-Term Debt', 'Share Capital',
  'Retained Earnings', 'Other Equity (AOCI, Treasury Stock, etc.)',
]

export const CF_ITEMS = [
  'Net Income', 'D&A Add-back', 'Amortization of Intangibles Add-back',
  'Changes in Working Capital', 'Operating Cash Flow', 'Capex',
  'Acquisitions / Disposals', 'Investing Cash Flow', 'Debt Issuance / Repayment',
  'Dividends Paid', 'Share Issuance / Buyback', 'Financing Cash Flow', 'Net Change in Cash',
]

export const SUBTOTALS = new Set([
  'Gross Profit', 'EBIT', 'EBITDA', 'EBT', 'Net Income',
  'Operating Cash Flow', 'Investing Cash Flow', 'Financing Cash Flow', 'Net Change in Cash',
])

// Costs are stored positive in the engine but should display as negative.
export const COST_LINES = new Set([
  'Cost of Goods Sold', 'SG&A', 'R&D', 'D&A', 'Amortization of Intangibles',
  'Other OpEx', 'Interest Expense', 'Tax',
])

/** Format with finance-style parentheses for negatives. */
export function fmtVal(
  raw: string | number | undefined,
  fmt: (v: any) => string
): { text: string; negative: boolean } {
  if (raw === undefined || raw === null || raw === '') return { text: '—', negative: false }
  const num = typeof raw === 'number' ? raw : parseFloat(String(raw))
  if (isNaN(num)) return { text: '—', negative: false }
  if (num < 0) {
    const pos = fmt(Math.abs(num))
    return { text: `(${pos})`, negative: true }
  }
  return { text: fmt(num), negative: false }
}

export function growth(curr: string | undefined, prev: string | undefined): string {
  const nc = parseFloat(String(curr ?? '0'))
  const np = parseFloat(String(prev ?? '0'))
  if (!np || isNaN(nc) || isNaN(np)) return '—'
  const g = ((nc - np) / Math.abs(np)) * 100
  return (g >= 0 ? '+' : '') + g.toFixed(1) + '%'
}
