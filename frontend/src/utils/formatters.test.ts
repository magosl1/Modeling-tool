import { describe, it, expect } from 'vitest'
import { formatNumberPure } from './formatters'

describe('formatNumberPure', () => {
  it('returns em-dash for nullish or empty input', () => {
    expect(formatNumberPure(null, 0, 'exact', 'us')).toBe('—')
    expect(formatNumberPure(undefined, 0, 'exact', 'us')).toBe('—')
    expect(formatNumberPure('', 0, 'exact', 'us')).toBe('—')
  })

  it('returns em-dash for non-numeric strings', () => {
    expect(formatNumberPure('not-a-number', 0, 'exact', 'us')).toBe('—')
  })

  it('scales by unit', () => {
    expect(formatNumberPure(1_500_000, 1, 'millions', 'us')).toBe('1.5')
    expect(formatNumberPure(2_500, 1, 'thousands', 'us')).toBe('2.5')
    expect(formatNumberPure(3_000_000_000, 2, 'billions', 'us')).toBe('3.00')
  })

  it('applies US separator style', () => {
    expect(formatNumberPure(1234567.89, 2, 'exact', 'us')).toBe('1,234,567.89')
  })

  it('applies EU separator style', () => {
    // de-DE uses "." as thousands separator and "," as decimal separator.
    expect(formatNumberPure(1234567.89, 2, 'exact', 'eu')).toBe('1.234.567,89')
  })

  it('honors the decimals argument', () => {
    expect(formatNumberPure(1, 0, 'exact', 'us')).toBe('1')
    expect(formatNumberPure(1, 3, 'exact', 'us')).toBe('1.000')
  })
})
