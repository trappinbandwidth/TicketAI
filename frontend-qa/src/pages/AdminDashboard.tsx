import { useEffect, useState, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import { adminApi } from '../api/admin'

// ── Brand tokens (from Rig Resolve brand guide) ───────────────────────────
const BRAND = {
  ink:      '#2D3142',
  inkDeep:  '#1A1E2E',
  teal:     '#2EC4A5',
  tealDark: '#1E9E85',
  tealTint: '#E8FAF6',
  offWhite: '#F8FAFC',
}

// ── Urgency config ────────────────────────────────────────────────────────
const URGENCY_ORDER: Record<string, number> = { CRITICAL: 0, HIGH: 1, STANDARD: 2, LOW: 3 }
const URGENCY_COLOR: Record<string, string> = {
  CRITICAL: '#DC2626',
  HIGH:     '#EA580C',
  STANDARD: '#2563EB',
  LOW:      '#6B7280',
}
const URGENCY_BG: Record<string, string> = {
  CRITICAL: '#FEE2E2',
  HIGH:     '#FFEDD5',
  STANDARD: '#DBEAFE',
  LOW:      '#F3F4F6',
}

const PASS_COLORS = { green: '#22c55e', yellow: '#eab308', red: '#ef4444', unknown: '#94a3b8' }
const HEALTH_COLOR = (h: number) => h >= 0.9 ? '#22c55e' : h >= 0.75 ? '#eab308' : '#ef4444'
const CONF_COLOR   = (c: number) => c >= 0.85 ? '#22c55e' : c >= 0.60 ? '#eab308' : '#ef4444'
const DOC_COLORS   = ['#6366f1','#3b82f6','#06b6d4','#10b981','#f59e0b','#f97316','#ec4899']

const PASS_BADGE: Record<string, string> = {
  green:  'bg-green-100 text-green-700',
  yellow: 'bg-yellow-100 text-yellow-700',
  red:    'bg-red-100 text-red-700',
}

const REVIEWERS = ['Quest', 'Justin', 'Eniola', 'Kevin'] as const
type Reviewer = typeof REVIEWERS[number]

function getStoredReviewer(): Reviewer {
  const stored = localStorage.getItem('rr_reviewer')
  return (REVIEWERS.includes(stored as Reviewer) ? stored : 'Quest') as Reviewer
}

// ── Small reusable components ─────────────────────────────────────────────
function KpiCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-col gap-1">
      <span className="text-xs text-gray-400 font-medium uppercase tracking-wide">{label}</span>
      <span className="text-2xl font-bold" style={{ color: color ?? BRAND.ink }}>{value}</span>
      {sub && <span className="text-xs text-gray-400">{sub}</span>}
    </div>
  )
}

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-4">
      <h2 className="text-lg font-bold" style={{ color: BRAND.ink }}>{title}</h2>
      {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
    </div>
  )
}

function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="w-8 h-8 border-2 border-gray-200 rounded-full"
        style={{ borderTopColor: BRAND.teal, animation: 'spin 0.8s linear infinite' }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}

// ── Tab navigation ────────────────────────────────────────────────────────
const TABS = ['Review Queue', 'Overview', 'Fields', 'Agents', 'Scan Feed', 'Attorneys'] as const
type Tab = typeof TABS[number]

// ── Main component ────────────────────────────────────────────────────────
export default function AdminDashboard() {
  const [tab, setTab] = useState<Tab>('Review Queue')
  const [days, setDays] = useState(30)
  const [queueCount, setQueueCount] = useState<number | null>(null)
  const [reviewer, setReviewer] = useState<Reviewer>(getStoredReviewer)

  function handleReviewerChange(r: Reviewer) {
    setReviewer(r)
    localStorage.setItem('rr_reviewer', r)
  }

  return (
    <div className="min-h-screen" style={{ background: BRAND.offWhite }}>
      {/* Header — Brand Ink */}
      <div className="px-6 py-4 flex items-center justify-between" style={{ background: BRAND.ink }}>
        <div>
          <div style={{ fontFamily: "'Inter', sans-serif", fontSize: 20, fontWeight: 900, letterSpacing: -0.5, color: '#F1F5F9' }}>
            rig<span style={{ color: BRAND.teal }}>(</span>resolve
            <span style={{ color: '#475569', fontSize: 12, fontWeight: 500, marginLeft: 12 }}>Operations</span>
          </div>
          <p className="text-xs mt-0.5" style={{ color: '#475569' }}>Ticket review queue &amp; AI performance analytics · Internal</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Reviewer selector */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs" style={{ color: '#475569' }}>Reviewer:</span>
            <div className="flex gap-1">
              {REVIEWERS.map(r => (
                <button
                  key={r}
                  onClick={() => handleReviewerChange(r)}
                  className="px-2.5 py-1 rounded-lg text-xs font-semibold transition-all"
                  style={reviewer === r
                    ? { background: BRAND.teal, color: BRAND.inkDeep }
                    : { background: 'rgba(255,255,255,0.08)', color: '#94A3B8' }}
                >{r}</button>
              ))}
            </div>
          </div>
          {/* Days filter */}
          <div className="flex items-center gap-1">
            <span className="text-xs" style={{ color: '#475569' }}>Last</span>
            {[7, 30, 90].map(d => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className="px-2.5 py-1 rounded-lg text-xs font-medium transition-all"
                style={days === d
                  ? { background: BRAND.teal, color: BRAND.inkDeep, fontWeight: 700 }
                  : { background: 'rgba(255,255,255,0.08)', color: '#94A3B8' }}
              >{d}d</button>
            ))}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200 px-6 flex gap-1">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5"
            style={tab === t
              ? { borderColor: BRAND.teal, color: BRAND.teal }
              : { borderColor: 'transparent', color: '#6B7280' }}
          >
            {t}
            {t === 'Review Queue' && queueCount !== null && queueCount > 0 && (
              <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full leading-none">{queueCount}</span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="p-6">
        {tab === 'Review Queue' && <ReviewQueueTab onCountChange={setQueueCount} reviewer={reviewer} />}
        {tab === 'Overview'     && <OverviewTab  days={days} />}
        {tab === 'Fields'       && <FieldsTab    days={days} />}
        {tab === 'Agents'       && <AgentsTab    days={days} />}
        {tab === 'Scan Feed'    && <ScanFeedTab  />}
        {tab === 'Attorneys'    && <AttorneysTab />}
      </div>
    </div>
  )
}

// ── Review Queue Tab ──────────────────────────────────────────────────────
function ReviewQueueTab({ onCountChange, reviewer }: { onCountChange: (n: number) => void; reviewer: Reviewer }) {
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
        // Sort: CRITICAL first, then by urgency level, then by court date (soonest first)
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
      await adminApi.rejectTicket(ticketId, rejectReason.trim(), reviewer)
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
    // Also flag overdue court dates regardless of AI urgency rating
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
            const isOpen      = expanded === t.ticket_id
            const isRejectOpen = rejecting === t.ticket_id
            const isBusy      = busy === t.ticket_id
            const urgency     = t.reviewer_summary?.urgency_level ?? t.urgency_level ?? 'STANDARD'
            const pass        = (t.pass_status ?? 'unknown').toLowerCase()
            const completeness = t.reviewer_summary?.completeness_score
            const isCritical  = urgency === 'CRITICAL'

            // Days until court date
            let daysUntilCourt: number | null = null
            let courtLabel = ''
            if (t.court_date) {
              try {
                const courtMs = new Date(t.court_date).getTime()
                const nowMs   = Date.now()
                daysUntilCourt = Math.round((courtMs - nowMs) / 86_400_000)
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

                {/* Urgency accent bar */}
                <div className="h-1" style={{ background: URGENCY_COLOR[urgency] ?? '#6B7280' }} />

                <div className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      {/* Badges row */}
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

                      {/* Violation title */}
                      <p className="text-sm font-bold truncate" style={{ color: BRAND.ink }}>
                        {t.violation_category || 'Unknown violation'} — {t.ticket_state || '?'}, {t.ticket_county || '?'}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5 truncate">{t.violation_description || 'No description'}</p>

                      {/* Meta row */}
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

                    {/* Actions */}
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

                  {/* Reject form */}
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

                {/* Expanded detail */}
                {isOpen && (
                  <div className="border-t border-gray-100 px-5 py-4 space-y-4" style={{ background: BRAND.offWhite }}>

                    {/* Urgency / reviewer summary */}
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

                    {/* Missing fields */}
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

                    {/* Extracted fields */}
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

                    {/* Attorney matches */}
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

// ── Overview Tab ──────────────────────────────────────────────────────────
function OverviewTab({ days }: { days: number }) {
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    adminApi.overview(days).then(setData).catch(console.error)
  }, [days])

  if (!data) return <Spinner />
  if (data.total === 0) return (
    <div className="text-center py-16 text-gray-400">No scans in the last {days} days. Run some scans first.</div>
  )

  const pct = (n: number) => `${(n * 100).toFixed(1)}%`
  const docTypeData = Object.entries(data.doc_type_breakdown || {}).map(([name, value]) => ({ name, value }))

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <KpiCard label="Total Scans" value={data.total} sub={`Last ${days} days`} />
        <KpiCard label="Green Rate" value={pct(data.green_rate)} color={PASS_COLORS.green} />
        <KpiCard label="Yellow Rate" value={pct(data.yellow_rate)} color={PASS_COLORS.yellow} />
        <KpiCard label="Red Rate" value={pct(data.red_rate)} color={PASS_COLORS.red} />
        <KpiCard label="Attorney Match" value={pct(data.attorney_match_rate)} sub="of ticket scans" />
        <KpiCard label="Price Estimated" value={pct(data.price_estimate_rate)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-5">
          <SectionHeader title="Daily Scan Volume" subtitle="Stacked by pass status" />
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.daily_volume || []} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={d => d.slice(5)} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Bar dataKey="green"  stackId="a" fill={PASS_COLORS.green}  />
              <Bar dataKey="yellow" stackId="a" fill={PASS_COLORS.yellow} />
              <Bar dataKey="red"    stackId="a" fill={PASS_COLORS.red}    />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <SectionHeader title="Doc Types" />
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={docTypeData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80}
                label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`} labelLine={false}>
                {docTypeData.map((_, i) => <Cell key={i} fill={DOC_COLORS[i % DOC_COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

// ── Fields Tab ────────────────────────────────────────────────────────────
function FieldsTab({ days: _days }: { days: number }) {
  const [data, setData] = useState<any>(null)
  const [docType, setDocType] = useState<string>('')
  const [sortBy, setSortBy] = useState<'accuracy' | 'empty_rate' | 'edit_rate'>('accuracy')
  const [drillField, setDrillField] = useState<string | null>(null)
  const [drillData, setDrillData] = useState<any>(null)

  useEffect(() => {
    setData(null)
    adminApi.fields(docType || undefined).then(setData).catch(console.error)
  }, [docType])

  const openDrill = useCallback((field: string) => {
    setDrillField(field)
    setDrillData(null)
    adminApi.fieldDrilldown(field).then(setDrillData).catch(console.error)
  }, [])

  const fields: any[] = data?.fields ?? []
  const sorted = [...fields].sort((a, b) => {
    if (sortBy === 'accuracy') return (a.accuracy ?? 1) - (b.accuracy ?? 1)
    if (sortBy === 'empty_rate') return b.empty_rate - a.empty_rate
    return b.edit_rate - a.edit_rate
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={docType}
          onChange={e => setDocType(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
        >
          <option value="">All Doc Types</option>
          {['Ticket','Inspection Report','Crash Report','Warning','Civil Penalty','CDL','MVR'].map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <span className="text-xs text-gray-400">Sort by:</span>
        {(['accuracy','empty_rate','edit_rate'] as const).map(s => (
          <button key={s} onClick={() => setSortBy(s)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
            style={sortBy === s ? { background: BRAND.teal, color: BRAND.inkDeep, fontWeight: 700 } : { background: '#F3F4F6', color: '#4B5563' }}
          >{s.replace('_', ' ')}</button>
        ))}
        {data && <span className="text-xs text-gray-400 ml-auto">{data.sample_size} approved scans</span>}
      </div>

      {!data ? <Spinner /> : (
        <>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['Field','Prompt Section','Accuracy','Avg Conf','Empty Rate','Edit Rate','Pass2 Help','Sample'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {sorted.map((f: any) => (
                  <tr key={f.field} onClick={() => openDrill(f.field)}
                    className="cursor-pointer transition-colors hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs font-medium" style={{ color: BRAND.ink }}>{f.field}</td>
                    <td className="px-4 py-3 text-xs text-gray-400">{f.prompt_section}</td>
                    <td className="px-4 py-3">
                      {f.accuracy != null ? (
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${f.accuracy * 100}%`, backgroundColor: CONF_COLOR(f.accuracy) }} />
                          </div>
                          <span className="text-xs font-medium" style={{ color: CONF_COLOR(f.accuracy) }}>
                            {(f.accuracy * 100).toFixed(1)}%
                          </span>
                        </div>
                      ) : <span className="text-xs text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-mono" style={{ color: CONF_COLOR(f.avg_confidence) }}>
                        {f.avg_confidence.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: f.empty_rate > 0.1 ? '#ef4444' : '#94a3b8' }}>
                      {(f.empty_rate * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: f.edit_rate > 0.15 ? '#f59e0b' : '#94a3b8' }}>
                      {(f.edit_rate * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400">
                      {f.pass2_improvement_rate > 0 ? (
                        <span style={{ color: BRAND.teal }}>+{(f.pass2_improvement_rate * 100).toFixed(0)}%</span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400">{f.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {sorted.length === 0 && (
              <div className="py-12 text-center text-gray-400 text-sm">
                No field data yet. Approve some scans to populate this table.
              </div>
            )}
          </div>

          {drillField && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-bold font-mono" style={{ color: BRAND.ink }}>{drillField}</h3>
                  {drillData && <p className="text-xs text-gray-400 mt-0.5">Prompt: {drillData.prompt_section}</p>}
                </div>
                <button onClick={() => setDrillField(null)} className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
              </div>
              {!drillData ? <Spinner /> : (
                <table className="w-full text-xs">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      {['File','Doc Type','Pass','AI Value','Human Correction','Conf','Pass1','Pass2','Wrong?'].map(h => (
                        <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-gray-500">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {drillData.cases.slice(0, 30).map((c: any, i: number) => (
                      <tr key={i} className={c.was_wrong ? 'bg-red-50' : ''}>
                        <td className="px-3 py-2 text-gray-600 max-w-[120px] truncate">{c.filename}</td>
                        <td className="px-3 py-2 text-gray-400">{c.doc_type || '—'}</td>
                        <td className="px-3 py-2">
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                            style={{ background: ((PASS_COLORS as any)[c.pass_status] ?? '#94a3b8') + '20', color: (PASS_COLORS as any)[c.pass_status] ?? '#94a3b8' }}>
                            {c.pass_status}
                          </span>
                        </td>
                        <td className="px-3 py-2 font-medium max-w-[140px] truncate" style={{ color: BRAND.ink }}>{c.ai_value || <span className="text-gray-300 italic">empty</span>}</td>
                        <td className="px-3 py-2 max-w-[140px] truncate" style={{ color: BRAND.teal }}>{c.final_value !== c.ai_value ? c.final_value : '—'}</td>
                        <td className="px-3 py-2 font-mono" style={{ color: CONF_COLOR(c.confidence) }}>{c.confidence.toFixed(2)}</td>
                        <td className="px-3 py-2 text-gray-400 max-w-[100px] truncate">{c.pass1_value || '—'}</td>
                        <td className="px-3 py-2 text-gray-400 max-w-[100px] truncate">{c.pass2_value || '—'}</td>
                        <td className="px-3 py-2">{c.was_wrong ? '✗' : '✓'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Agents Tab ────────────────────────────────────────────────────────────
function AgentsTab({ days }: { days: number }) {
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

// ── Scan Feed Tab ─────────────────────────────────────────────────────────
function ScanFeedTab() {
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    adminApi.feed(100).then(setData).catch(console.error)
  }, [])

  if (!data) return <Spinner />

  const scans: any[] = data.scans ?? []

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            {['Time','File','Doc Type','Pass','Prompt','Attorney','Estimate','Status'].map(h => (
              <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {scans.map((s: any) => (
            <tr key={s.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 text-xs text-gray-400 font-mono">{s.created_at?.slice(11, 16)}</td>
              <td className="px-4 py-3 text-xs font-medium max-w-[160px] truncate" style={{ color: BRAND.ink }}>{s.filename}</td>
              <td className="px-4 py-3 text-xs text-gray-500">{s.doc_type || '—'}</td>
              <td className="px-4 py-3">
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase"
                  style={{ background: ((PASS_COLORS as any)[s.pass_status] ?? '#94a3b8') + '20', color: (PASS_COLORS as any)[s.pass_status] ?? '#94a3b8' }}>
                  {s.pass_status}
                </span>
              </td>
              <td className="px-4 py-3 text-xs font-mono text-gray-400">{s.prompt_version || '—'}</td>
              <td className="px-4 py-3 text-xs">
                {s.attorney_matched
                  ? <span style={{ color: BRAND.tealDark }}>✓ {s.attorney_match_type}</span>
                  : <span className="text-gray-300">—</span>}
              </td>
              <td className="px-4 py-3 text-xs">
                {s.has_price_estimate
                  ? <span style={{ color: BRAND.teal }}>✓</span>
                  : <span className="text-gray-300">—</span>}
              </td>
              <td className="px-4 py-3">
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                  s.status === 'approved' ? 'bg-green-100 text-green-700' :
                  s.status === 'rejected' ? 'bg-red-100 text-red-700' :
                  'bg-gray-100 text-gray-500'}`}>
                  {s.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {scans.length === 0 && (
        <div className="py-12 text-center text-gray-400 text-sm">No scans yet.</div>
      )}
    </div>
  )
}

// ── Attorneys Tab ─────────────────────────────────────────────────────────
function AttorneysTab() {
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
