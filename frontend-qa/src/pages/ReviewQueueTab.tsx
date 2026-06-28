import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../api/admin'
import { BRAND, URGENCY_ORDER, URGENCY_COLOR, URGENCY_BG, PASS_BADGE } from '../shared/brandTokens'
import { Spinner } from '../shared/SharedComponents'
import type { Reviewer } from '../shared/brandTokens'

interface Props {
  onCountChange: (n: number) => void
  reviewer: Reviewer
}

export default function ReviewQueueTab({ onCountChange, reviewer }: Props) {
  const [tickets, setTickets] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [rejecting, setRejecting] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    adminApi.reviewQueue()
      .then((data: any) => {
        const raw: any[] = data.tickets ?? []
        const sorted = [...raw].sort((a, b) => {
          const ua = URGENCY_ORDER[a.reviewer_summary?.urgency_level ?? a.urgency_level ?? 'STANDARD'] ?? 2
          const ub = URGENCY_ORDER[b.reviewer_summary?.urgency_level ?? b.urgency_level ?? 'STANDARD'] ?? 2
          if (ua !== ub) return ua - ub
          const da = a.court_date ?? '9999'
          const db = b.court_date ?? '9999'
          return da.localeCompare(db)
        })
        setTickets(sorted)
        onCountChange(sorted.length)
      })
      .catch(() => setTickets([]))
      .finally(() => setLoading(false))
  }, [onCountChange])

  useEffect(() => { load() }, [load])

  function showToast(msg: string, ok: boolean) {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3500)
  }

  async function handleApprove(ticketId: string) {
    setBusy(ticketId)
    try {
      await adminApi.approveTicket(ticketId, reviewer)
      showToast(`Ticket approved by ${reviewer} — moved to New queue`, true)
      setTickets(prev => prev.filter(t => t.ticket_id !== ticketId))
      onCountChange(tickets.length - 1)
    } catch (e: any) {
      showToast(`Approve failed: ${e.message}`, false)
    } finally {
      setBusy(null)
    }
  }

  async function handleReject(ticketId: string) {
    if (!rejectReason.trim()) { showToast('Enter a rejection reason', false); return }
    setBusy(ticketId)
    try {
      await adminApi.rejectTicket(ticketId, rejectReason.trim())
      showToast(`Ticket rejected by ${reviewer}`, true)
      setTickets(prev => prev.filter(t => t.ticket_id !== ticketId))
      onCountChange(tickets.length - 1)
      setRejecting(null)
      setRejectReason('')
    } catch (e: any) {
      showToast(`Reject failed: ${e.message}`, false)
    } finally {
      setBusy(null)
    }
  }

  if (loading) return <Spinner />

  const criticals = tickets.filter(t => {
    const u = t.reviewer_summary?.urgency_level ?? t.urgency_level ?? ''
    if (u === 'CRITICAL') return true
    if (t.court_date) {
      const daysLeft = Math.round((new Date(t.court_date).getTime() - Date.now()) / 86_400_000)
      if (daysLeft < 0) return true
    }
    return false
  })

  return (
    <div className="space-y-4 max-w-4xl">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-xl shadow-lg text-sm font-medium ${toast.ok ? 'text-white' : 'bg-red-600 text-white'}`}
          style={toast.ok ? { background: BRAND.teal, color: BRAND.inkDeep } : undefined}>
          {toast.msg}
        </div>
      )}

      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold" style={{ color: BRAND.ink }}>Ticket Review Queue</h2>
          <p className="text-sm text-gray-400 mt-0.5">
            Reviewing as <span className="font-semibold" style={{ color: BRAND.teal }}>{reviewer}</span> · Approve to send to attorney queue, reject to discard
          </p>
        </div>
        <button
          onClick={load}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
        >
          ↻ Refresh
        </button>
      </div>

      {/* Critical alert banner */}
      {criticals.length > 0 && (
        <div className="rounded-xl border-2 border-red-200 p-4 flex items-start gap-3" style={{ background: '#FEF2F2' }}>
          <div className="text-xl flex-shrink-0 mt-0.5">🚨</div>
          <div className="flex-1">
            <div className="text-sm font-bold text-red-700 uppercase tracking-wide">
              {criticals.length} CRITICAL ticket{criticals.length > 1 ? 's' : ''} — immediate attention required
            </div>
            <div className="mt-1 space-y-0.5">
              {criticals.map(t => (
                <div key={t.ticket_id} className="text-xs text-red-600">
                  {t.driver_full_name || 'Unknown driver'} · {t.ticket_county}, {t.ticket_state} · Court: {t.court_date || 'Unknown'}
                  {t.reviewer_summary?.urgency_reason && (
                    <span className="text-red-400 ml-1">— {t.reviewer_summary.urgency_reason}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tickets.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 py-20 text-center">
          <div className="text-3xl mb-3">✓</div>
          <p className="text-gray-500 font-medium">Queue is clear</p>
          <p className="text-gray-300 text-xs mt-1">Upload a ticket with source=manual — it will appear here for review.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tickets.map((t: any) => {
            const isOpen       = expanded === t.ticket_id
            const isRejectOpen = rejecting === t.ticket_id
            const isBusy       = busy === t.ticket_id
            const urgency      = t.reviewer_summary?.urgency_level ?? t.urgency_level ?? 'STANDARD'
            const pass         = (t.pass_status ?? 'unknown').toLowerCase()
            const completeness = t.reviewer_summary?.completeness_score
            const isCritical   = urgency === 'CRITICAL'

            let daysUntilCourt: number | null = null
            let courtLabel = ''
            if (t.court_date) {
              try {
                const courtMs = new Date(t.court_date).getTime()
                daysUntilCourt = Math.round((courtMs - Date.now()) / 86_400_000)
                courtLabel = daysUntilCourt < 0
                  ? `${Math.abs(daysUntilCourt)}d overdue`
                  : daysUntilCourt === 0 ? 'TODAY'
                  : `${daysUntilCourt}d`
              } catch { /* ignore */ }
            }

            return (
              <div key={t.ticket_id}
                className="bg-white rounded-xl border overflow-hidden"
                style={{ borderColor: isCritical ? '#FECACA' : '#E5E7EB', borderWidth: isCritical ? 2 : 1 }}>

                <div className="h-1" style={{ background: URGENCY_COLOR[urgency] ?? '#6B7280' }} />

                <div className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-2">
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                          style={{ background: URGENCY_BG[urgency] ?? '#F3F4F6', color: URGENCY_COLOR[urgency] ?? '#6B7280' }}>
                          {urgency}
                        </span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${PASS_BADGE[pass] ?? 'bg-gray-100 text-gray-500'}`}>
                          {pass} scan
                        </span>
                        {completeness != null && (
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${completeness >= 0.8 ? 'bg-green-100 text-green-700' : completeness >= 0.6 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'}`}>
                            {Math.round(completeness * 100)}% complete
                          </span>
                        )}
                        {t.reviewer_summary?.cdl_mismatch && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700">
                            ⚠ CDL MISMATCH
                          </span>
                        )}
                      </div>

                      <p className="text-sm font-bold truncate" style={{ color: BRAND.ink }}>
                        {t.violation_category || 'Unknown violation'} — {t.ticket_state || '?'}, {t.ticket_county || '?'}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5 truncate">{t.violation_description || 'No description'}</p>

                      <div className="flex flex-wrap gap-3 mt-2 text-xs text-gray-400">
                        {t.driver_full_name && (
                          <span>Driver: <span className="font-semibold" style={{ color: BRAND.ink }}>{t.driver_full_name}</span></span>
                        )}
                        {t.court_date && (
                          <span>
                            Court: <span className="font-medium text-gray-700">{t.court_date}</span>
                            {courtLabel && (
                              <span className="ml-1 font-bold" style={{ color: daysUntilCourt !== null && daysUntilCourt <= 7 ? '#DC2626' : daysUntilCourt !== null && daysUntilCourt <= 30 ? '#D97706' : '#6B7280' }}>
                                ({courtLabel})
                              </span>
                            )}
                          </span>
                        )}
                        {t.citation_number && (
                          <span>Citation: <span className="font-mono text-gray-600">{t.citation_number}</span></span>
                        )}
                        {t.price_display && (
                          <span>Est: <span className="font-semibold" style={{ color: BRAND.tealDark }}>{t.price_display}</span></span>
                        )}
                      </div>
                    </div>

                    <div className="flex flex-col items-end gap-2 flex-shrink-0">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setExpanded(isOpen ? null : t.ticket_id)}
                          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
                        >
                          {isOpen ? 'Collapse' : 'Details'}
                        </button>
                        <button
                          disabled={isBusy}
                          onClick={() => { setRejecting(isRejectOpen ? null : t.ticket_id); setRejectReason('') }}
                          className="px-3 py-1.5 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                          style={{ background: '#FEF2F2', color: '#DC2626' }}
                        >
                          Reject
                        </button>
                        <button
                          disabled={isBusy}
                          onClick={() => handleApprove(t.ticket_id)}
                          className="px-4 py-1.5 text-xs font-bold rounded-lg transition-all disabled:opacity-50"
                          style={{ background: BRAND.teal, color: BRAND.inkDeep }}
                        >
                          {isBusy ? '…' : 'Approve →'}
                        </button>
                      </div>
                    </div>
                  </div>

                  {isRejectOpen && (
                    <div className="mt-3 flex items-center gap-2">
                      <input
                        value={rejectReason}
                        onChange={e => setRejectReason(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleReject(t.ticket_id)}
                        placeholder="Rejection reason (required)"
                        className="flex-1 text-xs border border-gray-300 rounded-lg px-3 py-2 outline-none"
                        style={{ fontFamily: "'Inter', sans-serif" }}
                        // eslint-disable-next-line jsx-a11y/no-autofocus
                        autoFocus
                      />
                      <button
                        disabled={isBusy || !rejectReason.trim()}
                        onClick={() => handleReject(t.ticket_id)}
                        className="px-4 py-2 text-xs font-bold rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50"
                      >
                        {isBusy ? '…' : 'Confirm Reject'}
                      </button>
                      <button
                        onClick={() => { setRejecting(null); setRejectReason('') }}
                        className="px-3 py-2 text-xs font-medium rounded-lg bg-gray-100 text-gray-500 hover:bg-gray-200 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>

                {isOpen && (
                  <div className="border-t border-gray-100 px-5 py-4 space-y-4" style={{ background: BRAND.offWhite }}>
                    {t.reviewer_summary && (
                      <div>
                        <p className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-2">AI Reviewer Summary</p>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
                          {t.reviewer_summary.urgency_reason && (
                            <div className="bg-white rounded-lg border border-gray-200 px-3 py-2 col-span-2 md:col-span-3">
                              <span className="text-gray-400 block">Urgency reason</span>
                              <span className="font-medium" style={{ color: URGENCY_COLOR[urgency] }}>{t.reviewer_summary.urgency_reason}</span>
                            </div>
                          )}
                          {t.reviewer_summary.cdl_match != null && (
                            <div className="bg-white rounded-lg border border-gray-200 px-3 py-2">
                              <span className="text-gray-400 block">CDL match</span>
                              <span className={`font-bold ${t.reviewer_summary.cdl_match ? 'text-green-600' : 'text-red-600'}`}>
                                {t.reviewer_summary.cdl_match ? '✓ Matched' : '✗ Mismatch'}
                              </span>
                            </div>
                          )}
                          {t.reviewer_summary.mvr_status && (
                            <div className="bg-white rounded-lg border border-gray-200 px-3 py-2">
                              <span className="text-gray-400 block">MVR status</span>
                              <span className="font-medium text-gray-700">{t.reviewer_summary.mvr_status}</span>
                            </div>
                          )}
                          {t.reviewer_summary.dual_conflicts != null && (
                            <div className="bg-white rounded-lg border border-gray-200 px-3 py-2">
                              <span className="text-gray-400 block">Dual conflicts</span>
                              <span className={`font-bold ${t.reviewer_summary.dual_conflicts > 0 ? 'text-amber-600' : 'text-green-600'}`}>
                                {t.reviewer_summary.dual_conflicts}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {t.reviewer_summary?.missing_critical_fields?.length > 0 && (
                      <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                        <p className="text-xs font-bold text-amber-700 mb-1">Missing critical fields</p>
                        <div className="flex flex-wrap gap-1">
                          {t.reviewer_summary.missing_critical_fields.map((f: string) => (
                            <span key={f} className="text-[10px] bg-amber-100 text-amber-700 px-2 py-0.5 rounded font-mono">{f}</span>
                          ))}
                        </div>
                      </div>
                    )}

                    <div>
                      <p className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-2">AI Extracted Fields</p>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
                        {([
                          ['Violation', t.violation_description],
                          ['Category', t.violation_category],
                          ['State', t.ticket_state],
                          ['County', t.ticket_county],
                          ['City', t.ticket_city],
                          ['Court Date', t.court_date],
                          ['Ticket Date', t.date_of_ticket],
                          ['Citation #', t.citation_number],
                          ['Driver CDL', t.driver_cdl],
                          ['Driver DOB', t.driver_dob],
                          ['Price', t.price_display],
                          ['Pass', t.pass_status],
                        ] as [string, string | undefined][]).map(([label, val]) => val ? (
                          <div key={label} className="bg-white rounded-lg border border-gray-200 px-3 py-2">
                            <span className="text-gray-400 block">{label}</span>
                            <span className="font-medium" style={{ color: BRAND.ink, fontFamily: label.includes('#') || label === 'Citation #' || label === 'Driver CDL' ? "'JetBrains Mono', monospace" : undefined }}>
                              {val}
                            </span>
                          </div>
                        ) : null)}
                      </div>
                    </div>

                    {(t.reviewer_summary?.attorney_matches ?? t.attorney_matches ?? []).length > 0 && (
                      <div>
                        <p className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-2">AI-Matched Attorneys</p>
                        <div className="space-y-1">
                          {(t.reviewer_summary?.attorney_matches ?? t.attorney_matches).map((a: any, idx: number) => (
                            <div key={a.attorney_id ?? idx} className="bg-white rounded-lg border border-gray-200 px-3 py-2 flex justify-between items-center text-xs">
                              <span className="font-semibold" style={{ color: BRAND.ink }}>{a.name}</span>
                              <div className="flex items-center gap-3 text-gray-400">
                                {a.phone && <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{a.phone}</span>}
                                {a.win_rate != null && (
                                  <span className="font-medium" style={{ color: BRAND.tealDark }}>{Math.round(a.win_rate * 100)}% win</span>
                                )}
                                {a.match_type && (
                                  <span className="px-2 py-0.5 rounded" style={{ background: BRAND.tealTint, color: BRAND.tealDark }}>{a.match_type}</span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
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
