import { useEffect, useState } from 'react'
import { adminApi } from '../api/admin'
import { BRAND, CONF_COLOR, HEALTH_COLOR } from '../shared/brandTokens'
import { Spinner } from '../shared/SharedComponents'

export default function AgentsTab({ days }: { days: number }) {
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    adminApi.agents(days).then(setData).catch(console.error)
  }, [days])

  if (!data) return <Spinner />

  const agents: any[] = data.agents ?? []

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...agents].sort((a, b) => b.health_score - a.health_score).map((ag: any) => (
          <div key={ag.agent} className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-lg mb-1">{ag.name}</div>
            <div className="text-2xl font-bold" style={{ color: HEALTH_COLOR(ag.health_score) }}>
              {(ag.health_score * 100).toFixed(0)}%
            </div>
            <div className="text-xs text-gray-400 mt-1">{ag.total_events} events · {ag.errors} errors</div>
            <div className="w-full h-1.5 bg-gray-200 rounded-full mt-2 overflow-hidden">
              <div className="h-full rounded-full transition-all"
                style={{ width: `${ag.health_score * 100}%`, backgroundColor: HEALTH_COLOR(ag.health_score) }} />
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {agents.map((ag: any) => (
          <div key={ag.agent} className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="font-bold" style={{ color: BRAND.ink }}>{ag.name}</span>
              <span className="text-sm font-bold px-2 py-1 rounded-lg"
                style={{ background: HEALTH_COLOR(ag.health_score) + '20', color: HEALTH_COLOR(ag.health_score) }}>
                {(ag.health_score * 100).toFixed(0)}% healthy
              </span>
            </div>

            {ag.agent === 'lone_ranger' && (
              <div className="space-y-3 text-sm">
                <div className="flex justify-between text-gray-600">
                  <span>Avg Pass 1 Fill Rate</span>
                  <span className="font-medium">{ag.avg_pass1_fill_rate} fields</span>
                </div>
                {ag.top_empty_fields?.length > 0 && (
                  <div>
                    <p className="text-xs text-red-500 font-semibold mb-1.5">⚠ Most often empty after Pass 1</p>
                    <div className="space-y-1">
                      {ag.top_empty_fields.slice(0, 6).map(([field, count]: [string, number]) => (
                        <div key={field} className="flex justify-between text-xs">
                          <span className="font-mono text-gray-600">{field}</span>
                          <span className="text-red-500 font-medium">{count}x</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {ag.top_low_conf_fields?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold mb-1.5" style={{ color: '#D97706' }}>⚡ Low confidence (Pass 1)</p>
                    <div className="space-y-1">
                      {ag.top_low_conf_fields.slice(0, 6).map(([field, count]: [string, number]) => (
                        <div key={field} className="flex justify-between text-xs">
                          <span className="font-mono text-gray-600">{field}</span>
                          <span className="font-medium" style={{ color: '#D97706' }}>{count}x</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {ag.agent === 'referee' && (
              <div className="space-y-3 text-sm">
                <div className="flex justify-between text-gray-600">
                  <span>Avg Confidence Score</span>
                  <span className="font-medium" style={{ color: CONF_COLOR(ag.avg_confidence_score) }}>
                    {ag.avg_confidence_score?.toFixed(3)}
                  </span>
                </div>
                {ag.top_critical_failures?.length > 0 && (
                  <div>
                    <p className="text-xs text-red-500 font-semibold mb-1.5">🚨 Critical field failures (→ RED)</p>
                    <div className="space-y-1">
                      {ag.top_critical_failures.map(([field, count]: [string, number]) => (
                        <div key={field} className="flex justify-between text-xs">
                          <span className="font-mono text-gray-600">{field}</span>
                          <span className="text-red-500 font-medium">{count}x</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {ag.top_low_conf_fields?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold mb-1.5" style={{ color: '#D97706' }}>⚡ Most flagged low-confidence fields</p>
                    <div className="space-y-1">
                      {ag.top_low_conf_fields.slice(0, 5).map(([field, count]: [string, number]) => (
                        <div key={field} className="flex justify-between text-xs">
                          <span className="font-mono text-gray-600">{field}</span>
                          <span className="font-medium" style={{ color: '#D97706' }}>{count}x</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {ag.agent === 'consensus' && (
              <div className="space-y-3 text-sm">
                <div className="flex justify-between text-gray-600">
                  <span>Avg improvements per scan</span>
                  <span className="font-medium" style={{ color: BRAND.teal }}>{ag.avg_improvements_per_scan}</span>
                </div>
                {ag.top_dual_conflict_fields?.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold mb-1.5" style={{ color: '#D97706' }}>⚠ Fields with dual conflicts</p>
                    <div className="space-y-1">
                      {ag.top_dual_conflict_fields.map(([field, count]: [string, number]) => (
                        <div key={field} className="flex justify-between text-xs">
                          <span className="font-mono text-gray-600">{field}</span>
                          <span className="font-medium" style={{ color: '#D97706' }}>{count}x</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {ag.agent === 'book_worm' && (
              <div className="space-y-3 text-sm">
                <div className="flex justify-between text-gray-600">
                  <span>Attorney recommended</span>
                  <span className="font-medium">{ag.attorney_recommended_count}</span>
                </div>
                <div className="flex justify-between text-gray-600">
                  <span>Zero-point tickets</span>
                  <span className="font-medium text-gray-400">{ag.zero_point_ticket_count}</span>
                </div>
                {ag.unknown_category_count > 0 && (
                  <div>
                    <p className="text-xs text-red-500 font-semibold mb-1.5">
                      🚨 Unknown categories ({ag.unknown_category_count}) — not in CDL_POINT_MAP
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {ag.unknown_categories?.map((cat: string) => (
                        <span key={cat} className="text-[10px] bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-mono">{cat}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {agents.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          No agent data yet. Run some scans and the agent scorecard will populate here.
        </div>
      )}
    </div>
  )
}
