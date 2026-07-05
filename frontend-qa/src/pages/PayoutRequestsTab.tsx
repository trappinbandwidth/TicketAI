import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../api/admin'
import { B, Spinner, Err, Badge, KpiCard, useToast } from '../shared/CpComponents'
import type { Reviewer } from '../shared/brandTokens'

const STATUS_FILTERS = ['all', 'pending', 'paid'] as const

export default function PayoutRequestsTab({ reviewer }: { reviewer: Reviewer }) {
  const [requests, setRequests] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [filter, setFilter] = useState<string>('pending')
  const [busy, setBusy] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const { show, el: toastEl } = useToast()

  const load = useCallback(() => {
    setLoading(true)
    setErr('')
    const status = filter === 'all' ? undefined : filter
    adminApi.payoutRequests(status)
      .then((r: any) => setRequests(r.payout_requests ?? []))
      .catch((e: any) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [filter])

  useEffect(() => { load() }, [load])

  async function handleMarkPaid(payoutId: string) {
    if (!confirm('Mark this payout as paid? This action cannot be undone.')) return
    setBusy(payoutId)
    try {
      await adminApi.markPayoutPaid(payoutId, reviewer)
      show('Payout marked as paid')
      load()
    } catch (e: any) { show(e.message, false) }
    finally { setBusy(null) }
  }

  const totalPending = requests
    .filter(r => r.status === 'pending')
    .reduce((sum: number, r: any) => sum + (r.total_amount ?? 0), 0)

  return (
    <div>
      {toastEl}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold" style={{ color: B.ink }}>Attorney Payout Requests</h2>
          <p className="text-sm text-gray-400 mt-0.5">Attorneys requesting payment for resolved cases</p>
        </div>
        <div className="flex gap-2">
          {STATUS_FILTERS.map(s => (
            <button key={s} onClick={() => setFilter(s)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all"
              style={filter === s
                ? { background: B.teal, color: '#fff' }
                : { background: '#F1F5F9', color: '#64748B' }}>
              {s}
            </button>
          ))}
        </div>
      </div>

      {filter !== 'paid' && totalPending > 0 && (
        <div className="grid grid-cols-2 gap-4 mb-6">
          <KpiCard label="Pending Payouts" value={requests.filter(r => r.status === 'pending').length} color={'#D97706'} />
          <KpiCard label="Total Pending ($)" value={`$${totalPending.toFixed(2)}`} color={'#D97706'} />
        </div>
      )}

      {loading && <Spinner />}
      {err && <Err msg={err} />}
      {!loading && !err && requests.length === 0 && (
        <div className="text-center py-20 text-gray-400">
          <div className="text-4xl mb-3">💸</div>
          <p className="font-medium">No payout requests in this status</p>
        </div>
      )}

      {!loading && !err && (
        <div className="space-y-3">
          {requests.map((req: any) => {
            const isOpen = expanded === req.payout_id
            return (
              <div key={req.payout_id} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div
                  className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => setExpanded(isOpen ? null : req.payout_id)}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 flex-wrap">
                      <span className="font-semibold text-sm" style={{ color: B.ink }}>
                        {req.attorney_name || req.attorney_id}
                      </span>
                      <Badge status={req.status} />
                      <span className="text-sm font-bold" style={{ color: req.status === 'pending' ? '#D97706' : B.teal }}>
                        ${(req.total_amount ?? 0).toFixed(2)}
                      </span>
                    </div>
                    <div className="text-xs text-gray-400 mt-1 flex gap-3 flex-wrap">
                      <span>{req.case_count ?? (req.case_ids ?? []).length} case(s)</span>
                      <span>Requested {req.requested_at ? new Date(req.requested_at).toLocaleDateString() : '—'}</span>
                      {req.paid_at && <span>Paid {new Date(req.paid_at).toLocaleDateString()}</span>}
                      {req.paid_by && <span>by {req.paid_by}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {req.status === 'pending' && (
                      <button
                        onClick={e => { e.stopPropagation(); handleMarkPaid(req.payout_id) }}
                        disabled={busy === req.payout_id}
                        className="text-xs px-4 py-2 rounded-lg font-semibold text-white disabled:opacity-50"
                        style={{ background: B.teal }}>
                        {busy === req.payout_id ? '…' : 'Mark Paid'}
                      </button>
                    )}
                    <span className="text-gray-300 text-sm">{isOpen ? '▲' : '▼'}</span>
                  </div>
                </div>

                {isOpen && (
                  <div className="border-t border-gray-100 px-5 py-4 bg-gray-50">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Included Cases</p>
                    {(req.cases ?? req.case_ids ?? []).length === 0
                      ? <p className="text-sm text-gray-400">No case detail available</p>
                      : (
                        <div className="space-y-2">
                          {(req.cases ?? req.case_ids ?? []).map((c: any, i: number) => (
                            <div key={typeof c === 'string' ? c : c.ticket_id ?? i}
                              className="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200 text-sm">
                              {typeof c === 'string'
                                ? <span className="font-mono text-gray-500 text-xs">{c}</span>
                                : (
                                  <>
                                    <div>
                                      <div className="font-medium text-gray-800">{c.violation_category || c.driver_full_name || c.ticket_id}</div>
                                      <div className="text-xs text-gray-400">{c.ticket_state} · {c.outcome || 'Resolved'}</div>
                                    </div>
                                    <span className="font-bold text-gray-700">${(c.attorney_fee_amount ?? 0).toFixed(2)}</span>
                                  </>
                                )}
                            </div>
                          ))}
                        </div>
                      )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
