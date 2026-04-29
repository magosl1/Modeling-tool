// Canonical financial line items. Mirror of backend/app/services/template_generator.py.
// When the backend list changes, update this file too.

export const CANONICAL_PNL = [
  'Revenue',
  'Cost of Goods Sold',
  'Gross Profit',
  'SG&A',
  'R&D',
  'D&A',
  'Amortization of Intangibles',
  'Other OpEx',
  'EBIT',
  'Interest Income',
  'Interest Expense',
  'Other Non-Operating Income / (Expense)',
  'EBT',
  'Tax',
  'Net Income',
] as const

export const CANONICAL_BS = [
  'PP&E Gross',
  'Accumulated Depreciation',
  'Net PP&E',
  'Intangibles Gross',
  'Accumulated Amortization',
  'Net Intangibles',
  'Goodwill',
  'Inventories',
  'Accounts Receivable',
  'Prepaid Expenses & Other Current Assets',
  'Cash & Equivalents',
  'Non-Operating Assets',
  'Share Capital',
  'Retained Earnings',
  'Other Equity (AOCI, Treasury Stock, etc.)',
  'Accounts Payable',
  'Accrued Liabilities',
  'Other Current Liabilities',
  'Other Long-Term Liabilities',
  'Short-Term Debt',
  'Long-Term Debt',
] as const

export const CANONICAL_CF = [
  'Net Income',
  'D&A Add-back',
  'Amortization of Intangibles Add-back',
  'Changes in Working Capital',
  'Operating Cash Flow',
  'Capex',
  'Acquisitions / Disposals',
  'Investing Cash Flow',
  'Debt Issuance / Repayment',
  'Dividends Paid',
  'Share Issuance / Buyback',
  'Financing Cash Flow',
  'Net Change in Cash',
] as const

export type CanonicalStatement = 'PNL' | 'BS' | 'CF'

export function statementOf(name: string): CanonicalStatement | null {
  if ((CANONICAL_PNL as readonly string[]).includes(name)) return 'PNL'
  if ((CANONICAL_BS as readonly string[]).includes(name)) return 'BS'
  if ((CANONICAL_CF as readonly string[]).includes(name)) return 'CF'
  return null
}

export const ALL_CANONICAL: { stmt: CanonicalStatement; name: string }[] = [
  ...CANONICAL_PNL.map((n) => ({ stmt: 'PNL' as const, name: n })),
  ...CANONICAL_BS.map((n) => ({ stmt: 'BS' as const, name: n })),
  ...CANONICAL_CF.map((n) => ({ stmt: 'CF' as const, name: n })),
]
