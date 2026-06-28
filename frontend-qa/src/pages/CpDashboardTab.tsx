import { useEffect, useState } from 'react'
import { controlApi } from '../api/admin'
import { B, Spinner, Err, KpiCard } from '../shared/CpComponents'

export default function CpDashboardTab() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  useEffect(() => {
    controlApi.kpi().then(setData).catch(e => setErr(e.message)).finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />
  if (err) return <Err msg={err} />
  if (!data) return null

  const casesByStatus = Object.entries(data.cases?.by_status ?? {}) as [string, number][]
  const ticketsByStatus = Object.entries(data.tickets?.by_status ?? {}) as [string, number][]

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-bold mb-4" style={{ color: B.ink }}>Business Overview</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard label="Total Drivers" value={data.drivers?.total ?? 0}
            sub={`${data.drivers?.active_memberships ?? 0} active memberships`} />
          <KpiCard label="Active Carriers" value={data.carriers?.active ?? 0}
            sub={`${data.carriers?.total ?? 0} total`} />
          <KpiCard label="Active Attorneys" value={data.attorneys?.active ?? 0}
            sub={`${data.attorneys?.pending_approval ?? 0} pending approval`}
            danger={(data.attorneys?.pending_approval ?? 0) > 0} />
          <KpiCard label="Pending Payouts" value={data.cases?.pending_payouts ?? 0}
            color="#7C3AED" danger={(data.cases?.pending_payouts ?? 0) > 0} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold mb-4" style={{ color: B.ink }}>Cases by Stage</h3>
          <div className="space-y-2">
            {casesByStatus.length === 0
              ? <p className="text-sm text-gray-400">No cases yet</p>
              : casesByStatus.sort((a, b) => b[1] - a[1]).map(([s, n]) => (
                <div key={s} className="flex items-center gap-3">
                  <div className="flex-1 text-sm font-medium text-gray-700 capitalize">{s.replace(/_/g, ' ')}</div>
                  <div className="w-32 bg-gray-100 rounded-full h-2 overflow-hidden">
                    <div className="h-full rounded-full" style={{
                      background: B.teal,
                      width: `${Math.round((n / (data.cases?.total || 1)) * 100)}%`
                    }} />
                  </div>
                  <div className="text-sm font-bold w-6 text-right" style={{ color: B.ink }}>{n}</div>
                </div>
              ))}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-bold mb-4" style={{ color: B.ink }}>Tickets by Status</h3>
          <div className="space-y-2">
            {ticketsByStatus.length === 0
              ? <p className="text-sm text-gray-400">No tickets yet</p>
              : ticketsByStatus.sort((a, b) => b[1] - a[1]).map(([s, n]) => (
                <div key={s} className="flex items-center gap-3">
                  <div className="flex-1 text-sm font-medium text-gray-700">{s}</div>
                  <div className="w-32 bg-gray-100 rounded-full h-2 overflow-hidden">
                    <div className="h-full rounded-full" style={{
                      background: s === 'New' ? '#3B82F6' : s === 'Accepted' ? '#22C55E' : s === 'AI Review' ? '#F59E0B' : '#94A3B8',
                      width: `${Math.round((n / (data.tickets?.total || 1)) * 100)}%`
                    }} />
                  </div>
                  <div className="text-sm font-bold w-6 text-right" style={{ color: B.ink }}>{n}</div>
                </div>
              ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <KpiCard label="Total Tickets" value={data.tickets?.total ?? 0} />
        <KpiCard label="Total Cases" value={data.cases?.total ?? 0} />
        <KpiCard label="Total Attorneys" value={data.attorneys?.total ?? 0} />
      </div>
    </div>
  )
}
