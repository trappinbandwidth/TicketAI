import { useEffect, useState } from 'react'
import { adminApi } from '../api/admin'
import { BRAND, CONF_COLOR } from '../shared/brandTokens'
import { Spinner } from '../shared/SharedComponents'

export default function AttorneysStatsTab() {
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    adminApi.attorneys().then(setData).catch(console.error)
  }, [])

  if (!data) return <Spinner />

  const states: any[] = data.by_state ?? []
  const noAtty: any[] = data.no_attorney_cases ?? []

  return (
    <div className="space-y-6">
      {noAtty.length > 0 && (
        <div className="rounded-xl border border-amber-200 p-4" style={{ background: '#FFFBEB' }}>
          <p className="text-sm font-semibold text-amber-700 mb-2">
            ⚠ {noAtty.length} recent scans with no attorney on file
          </p>
          <div className="flex flex-wrap gap-2">
            {noAtty.slice(0, 10).map((c: any, i: number) => (
              <span key={i} className="text-xs bg-white border border-amber-200 rounded px-2 py-1 text-amber-700">
                {c.state}{c.county ? ` — ${c.county}` : ''}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {['State','Total Tickets','Matched','No Match','Match Rate','County Match','Avg Win Rate'].map(h => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {states.map((s: any) => (
              <tr key={s.state} className={s.match_rate < 0.5 ? 'bg-red-50' : ''}>
                <td className="px-4 py-3 font-medium" style={{ color: BRAND.ink }}>{s.state}</td>
                <td className="px-4 py-3 text-gray-600">{s.total_tickets}</td>
                <td className="px-4 py-3 font-medium" style={{ color: BRAND.tealDark }}>{s.matched}</td>
                <td className="px-4 py-3 text-red-500">{s.no_match}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-12 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${s.match_rate * 100}%`, backgroundColor: CONF_COLOR(s.match_rate) }} />
                    </div>
                    <span className="text-xs" style={{ color: CONF_COLOR(s.match_rate) }}>{(s.match_rate * 100).toFixed(0)}%</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">{(s.county_match_rate * 100).toFixed(0)}%</td>
                <td className="px-4 py-3 text-xs text-gray-500">{s.avg_win_rate > 0 ? `${(s.avg_win_rate * 100).toFixed(0)}%` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {states.length === 0 && (
          <div className="py-12 text-center text-gray-400 text-sm">No ticket scan data yet.</div>
        )}
      </div>
    </div>
  )
}
