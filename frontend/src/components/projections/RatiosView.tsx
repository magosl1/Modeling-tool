import { useQuery } from '@tanstack/react-query'
import { ratiosApi } from '../../services/api'
import { useFormatNumber } from '../../utils/formatters'

interface Props { projectId: string; allModulesComplete?: boolean }

export default function RatiosView({ projectId }: Props) {
  const fmt = useFormatNumber()

  const { data, isLoading } = useQuery({
    queryKey: ['ratios', projectId],
    queryFn: () => ratiosApi.get(projectId).then(r => r.data),
  })

  if (isLoading) {
    return <div className="text-gray-500 py-8 text-center">Loading ratios...</div>
  }

  if (!data?.years?.length) {
    return (
      <div className="card text-center py-16">
        <p className="text-gray-500 mb-4">No data available. Run projections first.</p>
      </div>
    )
  }

  const { ratios, years } = data

  return (
    <div className="card space-y-8">
      {Object.entries(ratios).map(([category, metrics]) => (
        <div key={category} className="mb-8">
          <h3 className="font-semibold text-gray-800 mb-3 text-lg border-b border-gray-200 pb-2">{category}</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 pr-4 font-medium text-gray-600 w-64">Metric</th>
                  {years.map((y: string | number) => (
                    <th key={y} className="text-right py-2 px-3 font-medium text-blue-600 min-w-24">{y}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(metrics as any).map(([metricName, yearVals]) => (
                  <tr key={metricName} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 pr-4 text-gray-700 font-medium">{metricName}</td>
                    {years.map((y: string | number) => {
                      const val = (yearVals as any)[y]
                      const num = val !== undefined ? Number(val) : NaN
                      return (
                        <td key={y} className="py-2 px-3 text-right text-gray-900 tabular-nums">
                          {!isNaN(num) ? fmt(num) : '—'}
                          {metricName.includes('%') && !isNaN(num) && '%'}
                          {metricName.includes('Margin') && !metricName.includes('%') && !isNaN(num) && '%'}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  )
}
