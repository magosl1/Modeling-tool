import { AssumptionItem } from './constants'

type PxQField = AssumptionItem & {
  price?: { method?: string; growth_rate?: number | string; fixed_values?: Record<string, any> }
  quantity?: { method?: string; growth_rate?: number | string; fixed_values?: Record<string, any> }
}

/** Custom Price × Quantity sub-form used when projection_method === 'price_quantity'. */
export default function PxQForm({
  item,
  itemIdx,
  projectionYears,
  updatePxQ,
}: {
  item: PxQField
  itemIdx: number
  projectionYears: number[]
  updatePxQ: (idx: number, field: 'price' | 'quantity', sub: string, val: any) => void
}) {
  const price = item.price || { method: 'growth_flat', growth_rate: 0 }
  const quantity = item.quantity || { method: 'growth_flat', growth_rate: 0 }

  return (
    <div className="grid grid-cols-2 gap-4 bg-gray-50 rounded-lg p-3 mt-2">
      <SubForm
        label="Price"
        cfg={price}
        projectionYears={projectionYears}
        onChange={(sub, val) => updatePxQ(itemIdx, 'price', sub, val)}
      />
      <SubForm
        label="Quantity"
        cfg={quantity}
        projectionYears={projectionYears}
        onChange={(sub, val) => updatePxQ(itemIdx, 'quantity', sub, val)}
      />
    </div>
  )
}

function SubForm({
  label,
  cfg,
  projectionYears,
  onChange,
}: {
  label: string
  cfg: { method?: string; growth_rate?: number | string; fixed_values?: Record<string, any> }
  projectionYears: number[]
  onChange: (sub: string, val: any) => void
}) {
  const isFixed = cfg.method === 'fixed'
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-gray-600">{label}</p>
      <div>
        <label className="label text-xs">Method</label>
        <select
          className="input text-sm"
          value={cfg.method || 'growth_flat'}
          onChange={e => onChange('method', e.target.value)}
        >
          <option value="growth_flat">Flat Growth Rate</option>
          <option value="fixed">Fixed per Year</option>
        </select>
      </div>
      {!isFixed ? (
        <div>
          <label className="label text-xs">Annual Growth (%)</label>
          <input
            type="number"
            step="0.1"
            className="input text-sm"
            value={cfg.growth_rate ?? ''}
            onChange={e => onChange('growth_rate', e.target.value)}
            placeholder="e.g. 3"
          />
        </div>
      ) : (
        <div className="space-y-1">
          <label className="label text-xs">Value per Year</label>
          {projectionYears.map(y => (
            <div key={y} className="flex gap-2 items-center">
              <span className="text-xs text-gray-500 w-10">{y}</span>
              <input
                type="number"
                step="0.01"
                className="input text-sm flex-1"
                value={cfg.fixed_values?.[y] ?? ''}
                onChange={e => onChange(`fixed_${y}`, e.target.value)}
                placeholder={label}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
