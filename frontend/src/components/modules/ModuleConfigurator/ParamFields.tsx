import { AssumptionItem, ParamDef } from './constants'

/** Renders the parameter inputs for a single assumption item.
 *  Handles three layouts: optional (greyed) / per-year grid / single value.
 */
export default function ParamFields({
  item,
  itemIdx,
  paramDefs,
  projectionYears,
  updateParam,
  updatePerYearParam,
}: {
  item: AssumptionItem
  itemIdx: number
  paramDefs: ParamDef[]
  projectionYears: number[]
  updateParam: (idx: number, paramKey: string, value: string) => void
  updatePerYearParam: (idx: number, paramKey: string, year: number, value: string) => void
}) {
  if (paramDefs.length === 0) return null

  return (
    <div className="grid grid-cols-2 gap-3 bg-gray-50 rounded-lg p-3">
      {paramDefs.map(pd => {
        if (pd.optional && pd.key === 'base_value') {
          const param = item.params.find(p => p.param_key === pd.key && p.year === null)
          return (
            <div key={pd.key}>
              <label className="label text-xs text-gray-400">{pd.label}</label>
              <input
                type={pd.type || 'text'}
                className="input text-sm"
                value={param?.value || ''}
                onChange={e => updateParam(itemIdx, pd.key, e.target.value)}
                placeholder="Leave blank to use historical"
              />
            </div>
          )
        }
        if (pd.perYear && projectionYears.length > 0) {
          return (
            <div key={pd.key} className="col-span-2 space-y-2">
              <label className="label text-xs">{pd.label}</label>
              <div className="grid grid-cols-5 gap-2">
                {projectionYears.map(year => {
                  const param = item.params.find(p => p.param_key === pd.key && p.year === year)
                  return (
                    <div key={year}>
                      <label className="text-[10px] text-gray-500 mb-1 block">{year}</label>
                      <input
                        type={pd.type || 'text'}
                        className="input text-sm p-1.5"
                        value={param?.value || ''}
                        onChange={e => updatePerYearParam(itemIdx, pd.key, year, e.target.value)}
                        placeholder="---"
                      />
                    </div>
                  )
                })}
              </div>
            </div>
          )
        }
        const param = item.params.find(p => p.param_key === pd.key && p.year === null)
        return (
          <div key={pd.key}>
            <label className="label text-xs">{pd.label}</label>
            <input
              type={pd.type || 'text'}
              className="input text-sm"
              value={param?.value || ''}
              onChange={e => updateParam(itemIdx, pd.key, e.target.value)}
              placeholder="Enter value"
            />
          </div>
        )
      })}
    </div>
  )
}
