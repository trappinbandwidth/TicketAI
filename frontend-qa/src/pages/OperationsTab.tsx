import { useState } from 'react'
import { adminApi } from '../api/admin'

const BRAND = {
  ink:      '#2D3142',
  teal:     '#2EC4A5',
  tealDark: '#1E9E85',
  tealTint: '#E8FAF6',
}

const URGENCY_COLOR: Record<string, string> = {
  CRITICAL: '#DC2626', HIGH: '#EA580C', STANDARD: '#2563EB', LOW: '#6B7280',
}
const URGENCY_BG: Record<string, string> = {
  CRITICAL: '#FEF2F2', HIGH: '#FFF7ED', STANDARD: '#EFF6FF', LOW: '#F9FAFB',
}

function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="w-7 h-7 border-2 border-gray-200 rounded-full"
        style={{ borderTopColor: BRAND.teal, animation: 'spin 0.8s linear infinite' }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}

function SectionHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between mb-3">
      <div>
        <h3 className="text-base font-bold" style={{ color: BRAND.ink }}>{title}</h3>
        {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

// ── Court Deadline Monitor ────────────────────────────────────────────────

function CourtDeadlines() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function run() {
    setLoading(true)
    setError('')
    try {
      const result = await adminApi.courtDeadlines(false)
      setData(result)
    } catch (e: any) {
      setError(e.message || 'Failed to load court deadlines')
    } finally {
      setLoading(false)
    }
  }

  const BUCKETS = ['CRITICAL', 'HIGH', 'STANDARD', 'LOW', 'NO_DATE'] as const

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <SectionHeader
        title="Court Deadline Monitor"
        subtitle="Daily priority work queue — sorted by urgency and court date proximity"
        action={
          <button
            onClick={run}
            disabled={loading}
            className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
            style={{ background: BRAND.teal }}>
            {loading ? 'Running…' : data ? 'Refresh' : 'Run Now'}
          </button>
        }
      />

      {loading && <Spinner />}
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}

      {data && !loading && (
        <div className="space-y-4 mt-4">
          {/* Summary row */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: 'Total Open', value: data.total_open, color: BRAND.ink },
              { label: 'Critical', value: data.critical_count, color: '#DC2626' },
              { label: 'High', value: data.high_count, color: '#EA580C' },
              { label: 'No Date', value: data.no_date_count, color: '#6B7280' },
            ].map(k => (
              <div key={k.label} className="rounded-lg border border-gray-100 p-3 text-center">
                <p className="text-2xl font-bold" style={{ color: k.color }}>{k.value}</p>
                <p className="text-xs text-gray-400 mt-0.5">{k.label}</p>
              </div>
            ))}
          </div>

          {/* Buckets */}
          {BUCKETS.map(bucket => {
            const tickets: any[] = data.work_queue?.[bucket] ?? []
            if (tickets.length === 0) return null
            return (
              <div key={bucket}>
                <p className="text-xs font-bold uppercase tracking-wide mb-2"
                  style={{ color: URGENCY_COLOR[bucket] ?? '#6B7280' }}>
                  {bucket === 'NO_DATE' ? 'No Court Date' : bucket} ({tickets.length})
                </p>
                <div className="rounded-xl overflow-hidden border border-gray-100">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        {['Driver', 'Violation', 'State', 'Court Date', 'Days', 'Attorney', 'Status'].map(h => (
                          <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-gray-400 uppercase">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {tickets.map((t: any, i: number) => (
                        <tr key={t.ticket_id ?? i}
                          style={{ background: URGENCY_BG[bucket] ?? 'white' }}>
                          <td className="px-3 py-2 font-medium text-xs" style={{ color: BRAND.ink }}>{t.driver_name || '—'}</td>
                          <td className="px-3 py-2 text-xs text-gray-600 max-w-[140px] truncate">{t.violation || '—'}</td>
                          <td className="px-3 py-2 text-xs text-gray-500">{t.state || '—'}</td>
                          <td className="px-3 py-2 text-xs text-gray-600">{t.court_date || '—'}</td>
                          <td className="px-3 py-2 text-xs font-bold" style={{ color: URGENCY_COLOR[bucket] ?? '#6B7280' }}>
                            {t.days_until_court != null ? (t.days_until_court < 0 ? `${Math.abs(t.days_until_court)}d ago` : `${t.days_until_court}d`) : '—'}
                          </td>
                          <td className="px-3 py-2 text-xs text-gray-500">{t.attorney_name || 'Unassigned'}</td>
                          <td className="px-3 py-2">
                            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
                              {t.attorney_status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )
          })}

          <p className="text-xs text-gray-300 text-right">Run at {data.run_at?.slice(0, 16)?.replace('T', ' ')}</p>
        </div>
      )}

      {!data && !loading && !error && (
        <p className="text-sm text-gray-400 mt-4 text-center py-8">
          Click "Run Now" to generate today's priority work queue.
        </p>
      )}
    </div>
  )
}

// ── Payment Alerts ────────────────────────────────────────────────────────

function PaymentAlerts() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function run() {
    setLoading(true)
    setError('')
    try {
      setData(await adminApi.paymentAlerts())
    } catch (e: any) {
      setError(e.message || 'Failed to load payment alerts')
    } finally {
      setLoading(false)
    }
  }

  function AlertCard({ driver, type }: { driver: any; type: string }) {
    const isCritical = type === 'OPEN_CASE_LAPSED'
    return (
      <div className={`rounded-lg border p-3 ${isCritical ? 'border-red-200 bg-red-50' : type === 'EXPIRING_SOON' ? 'border-amber-200 bg-amber-50' : 'border-gray-200'}`}>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-semibold" style={{ color: BRAND.ink }}>{driver.name}</p>
            <p className="text-xs text-gray-500 mt-0.5">{driver.email} · {driver.plan || '—'}</p>
          </div>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
            isCritical ? 'bg-red-600 text-white' :
            type === 'EXPIRING_SOON' ? 'bg-amber-500 text-white' :
            'bg-gray-200 text-gray-600'}`}>
            {isCritical ? 'Open Case + Lapsed' : type === 'EXPIRING_SOON' ? `Expires in ${driver.days_left}d` : 'Lapsed'}
          </span>
        </div>
        {driver.expires && (
          <p className="text-xs text-gray-400 mt-1">
            {type === 'EXPIRING_SOON' ? 'Expires' : 'Expired'}: {driver.expires}
          </p>
        )}
        {driver.open_cases?.length > 0 && (
          <p className="text-xs text-red-600 mt-1 font-medium">
            Open case: {driver.open_cases[0]}
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <SectionHeader
        title="Payment Alerts"
        subtitle="Lapsed subscriptions and drivers expiring within 7 days"
        action={
          <button
            onClick={run}
            disabled={loading}
            className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
            style={{ background: BRAND.ink }}>
            {loading ? 'Loading…' : data ? 'Refresh' : 'Load Alerts'}
          </button>
        }
      />

      {loading && <Spinner />}
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}

      {data && !loading && (
        <div className="space-y-5 mt-4">
          {/* Summary */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Open Case + Lapsed', value: data.critical_count, color: '#DC2626' },
              { label: 'Lapsed (no case)', value: data.lapsed_count, color: '#6B7280' },
              { label: 'Expiring Soon', value: data.expiring_soon_count, color: '#D97706' },
            ].map(k => (
              <div key={k.label} className="rounded-lg border border-gray-100 p-3 text-center">
                <p className="text-2xl font-bold" style={{ color: k.color }}>{k.value}</p>
                <p className="text-xs text-gray-400 mt-0.5">{k.label}</p>
              </div>
            ))}
          </div>

          {data.critical?.length > 0 && (
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-red-600 mb-2">
                Critical — Open Case + Lapsed ({data.critical.length})
              </p>
              <div className="space-y-2">
                {data.critical.map((d: any) => <AlertCard key={d.driver_id} driver={d} type="OPEN_CASE_LAPSED" />)}
              </div>
            </div>
          )}

          {data.expiring_soon?.length > 0 && (
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-amber-600 mb-2">
                Expiring Soon ({data.expiring_soon.length})
              </p>
              <div className="space-y-2">
                {data.expiring_soon.map((d: any) => <AlertCard key={d.driver_id} driver={d} type="EXPIRING_SOON" />)}
              </div>
            </div>
          )}

          {data.lapsed?.length > 0 && (
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-2">
                Lapsed — No Open Case ({data.lapsed.length})
              </p>
              <div className="space-y-2">
                {data.lapsed.map((d: any) => <AlertCard key={d.driver_id} driver={d} type="LAPSED" />)}
              </div>
            </div>
          )}

          {data.critical_count === 0 && data.lapsed_count === 0 && data.expiring_soon_count === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">No payment alerts. All subscriptions look good.</p>
          )}

          <p className="text-xs text-gray-300 text-right">Run at {data.run_at?.slice(0, 16)?.replace('T', ' ')}</p>
        </div>
      )}

      {!data && !loading && !error && (
        <p className="text-sm text-gray-400 mt-4 text-center py-8">
          Click "Load Alerts" to check subscription status.
        </p>
      )}
    </div>
  )
}

// ── Main OperationsTab export ─────────────────────────────────────────────

export default function OperationsTab() {
  return (
    <div className="space-y-5">
      <CourtDeadlines />
      <PaymentAlerts />
    </div>
  )
}
