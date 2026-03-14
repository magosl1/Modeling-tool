import { create } from 'zustand'

export type NumericsUnit = 'exact' | 'thousands' | 'millions' | 'billions'
export type NumberSeparatorStyle = 'us' | 'eu'

interface FormattingState {
  decimals: number
  unit: NumericsUnit
  separatorStyle: NumberSeparatorStyle
  
  setDecimals: (d: number) => void
  setUnit: (u: NumericsUnit) => void
  setSeparatorStyle: (s: NumberSeparatorStyle) => void
}

export const useFormattingStore = create<FormattingState>()((set) => ({
  decimals: 0,
  unit: 'exact',
  separatorStyle: 'us',

  setDecimals: (decimals) => set({ decimals }),
  setUnit: (unit) => set({ unit }),
  setSeparatorStyle: (separatorStyle) => set({ separatorStyle }),
}))
