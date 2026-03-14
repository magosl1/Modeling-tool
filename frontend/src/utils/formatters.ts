import { useFormattingStore, NumericsUnit, NumberSeparatorStyle } from '../store/formattingStore'

export function formatNumberPure(
  val: string | number | undefined | null,
  decimals: number,
  unit: NumericsUnit,
  style: NumberSeparatorStyle
): string {
  if (val === undefined || val === null || val === '') return '—'
  let n = typeof val === 'string' ? parseFloat(val) : val
  if (isNaN(n)) return '—'

  // Apply units
  if (unit === 'thousands') n /= 1_000
  else if (unit === 'millions') n /= 1_000_000
  else if (unit === 'billions') n /= 1_000_000_000

  // Determine locale based on style
  const locale = style === 'eu' ? 'de-DE' : 'en-US'

  return n.toLocaleString(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

export function useFormatNumber() {
  const { decimals, unit, separatorStyle } = useFormattingStore()
  return (val: string | number | undefined | null) => 
    formatNumberPure(val, decimals, unit, separatorStyle)
}
