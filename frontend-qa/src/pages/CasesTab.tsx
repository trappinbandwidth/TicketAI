import { useEffect, useState, useCallback, useRef } from 'react'
import { adminApi, controlApi } from '../api/admin'

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

const CASE_STATUS_LABELS: Record<string, string> = {
  pending_approval: 'Pending Approval',
  active: 'Active',
  attorney_declined: 'Atty Declined',
  outcome_logged: 'Outcome Logged',
  payout_sent: 'Payout Sent',
  closed: 'Closed',
  rejected: 'Rejected',
}

const CASE_STATUS_NEXT: Record<string, { label: string; value: string }[]> = {
  pending_approval: [
    { label: 'Attorney Contacted', value: 'pending_approval' },
    { label: 'Attorney Accepted → Active', value: 'active' },
    { label: 'Attorney Declined', value: 'attorney_declined' },
  ],
  active: [
    { label: 'Log Outcome', value: 'outcome_logged' },
    { label: 'Mark Closed', value: 'closed' },
  ],
  attorney_declined: [
    { label: 'Reassign (create new case)', value: '' },
  ],
  outcome_logged: [
    { label: 'Mark Payout Sent', value: 'payout_sent' },
  ],
  payout_sent: [
    { label: 'Close Case', value: 'closed' },
  ],
}

const OUTCOMES = ['won', 'dismissed', 'reduced', 'lost', 'transferred']

function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="w-8 h-8 border-2 border-gray-200 rounded-full"
        style={{ borderTopColor: BRAND.teal, animation: 'spin 0.8s linear infinite' }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}

function UrgencyBadge({ level }: { level: string }) {
  return (
    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase"
      style={{ color: URGENCY_COLOR[level] ?? '#6B7280', background: URGENCY_BG[level] ?? '#F9FAFB' }}>
      {level}
    </span>
  )
}

function Toast({ msg, ok, onDone }: { msg: string; ok: boolean; onDone: () => void }) {
  useEffect(() => { const t = setTimeout(onDone, 3500); return () => clearTimeout(t) }, [onDone])
  return (
    <div className="fixed bottom-6 right-6 z-50 px-5 py-3 rounded-xl shadow-lg text-sm font-medium text-white"
      style={{ background: ok ? BRAND.tealDark : '#DC2626' }}>
      {msg}
    </div>
  )
}

// ── Assign Attorney Modal ──────────────────────────────────────────────────

function AssignModal({
  ticket,
  reviewer,
  onClose,
  onSuccess,
}: {
  ticket: any
  reviewer: string
  onClose: () => void
  onSuccess: () => void
}) {
  const [attorneys, setAttorneys] = useState<any[]>([])
  const [selectedAtty, setSelectedAtty] = useState('')
  const [contactMethod, setContactMethod] = useState('phone')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    adminApi.attorneysList().then(d => setAttorneys(d.attorneys ?? [])).catch(() => setAttorneys([]))
  }, [])

  // Auto-suggest attorneys by ticket state
  const suggested = attorneys.filter(a =>
    a.states_licensed?.includes(ticket.ticket_state) ||
    a.counties_covered?.some((c: string) => c.startsWith(`${ticket.ticket_state}:`))
  )
  const other = attorneys.filter(a => !suggested.includes(a))

  async function handleAssign() {
    if (!selectedAtty) { setError('Select an attorney'); return }
    setBusy(true)
    setError('')
    try {
      await adminApi.createCase({
        ticket_id: ticket.ticket_id,
        attorney_id: selectedAtty,
        assigned_by: reviewer,
        contact_method: contactMethod,
        note: note.trim() || undefined,
      })
      onSuccess()
    } catch (e: any) {
      setError(e.message || 'Assignment failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.4)' }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100" style={{ background: BRAND.tealTint }}>
          <p className="text-xs font-bold uppercase tracking-wide" style={{ color: BRAND.tealDark }}>Assign Attorney</p>
          <p className="font-semibold mt-0.5" style={{ color: BRAND.ink }}>
            {ticket.driver_name} — {ticket.violation_category}
          </p>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs text-gray-500">{ticket.ticket_state} · {ticket.ticket_county}</span>
            {ticket.court_date && <span className="text-xs text-gray-500">Court: {ticket.court_date}</span>}
            <UrgencyBadge level={ticket.urgency_level} />
          </div>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1.5">Select Attorney</label>
            {attorneys.length === 0 ? (
              <p className="text-sm text-gray-400">Loading attorneys…</p>
            ) : (
              <select
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2"
                style={{ '--tw-ring-color': BRAND.teal } as any}
                value={selectedAtty}
                onChange={e => setSelectedAtty(e.target.value)}
              >
                <option value="">— Choose attorney —</option>
                {suggested.length > 0 && (
                  <optgroup label={`Recommended for ${ticket.ticket_state}`}>
                    {suggested.map(a => (
                      <option key={a.attorney_id} value={a.attorney_id}>
                        {a.full_name} · {a.firm_name} · {a.tier} · {((a.win_rate ?? 0) * 100).toFixed(0)}% win rate
                      </option>
                    ))}
                  </optgroup>
                )}
                {other.length > 0 && (
                  <optgroup label="Other Attorneys">
                    {other.map(a => (
                      <option key={a.attorney_id} value={a.attorney_id}>
                        {a.full_name} · {a.firm_name} · {a.states_licensed?.join(', ')}
                      </option>
                    ))}
                  </optgroup>
                )}
              </select>
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1.5">Contact Method</label>
            <div className="flex gap-2">
              {['phone', 'email', 'text'].map(m => (
                <button key={m}
                  onClick={() => setContactMethod(m)}
                  className={`px-4 py-1.5 rounded-lg text-sm capitalize font-medium border transition-colors ${contactMethod === m ? 'border-transparent text-white' : 'border-gray-200 text-gray-500 hover:border-gray-300'}`}
                  style={contactMethod === m ? { background: BRAND.teal } : {}}>
                  {m}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1.5">Note (optional)</label>
            <textarea
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none"
              rows={2}
              placeholder="e.g. Called main office, left message"
              value={note}
              onChange={e => setNote(e.target.value)}
            />
          </div>

          {error && <p className="text-red-600 text-sm">{error}</p>}
        </div>

        <div className="px-6 pb-5 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-500 hover:bg-gray-50">
            Cancel
          </button>
          <button
            onClick={handleAssign}
            disabled={busy || !selectedAtty}
            className="px-5 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-40 transition-opacity"
            style={{ background: BRAND.teal }}>
            {busy ? 'Assigning…' : 'Assign Attorney'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Record Outcome Modal ───────────────────────────────────────────────────

function OutcomeModal({
  caseData,
  reviewer,
  onClose,
  onSuccess,
}: {
  caseData: any
  reviewer: string
  onClose: () => void
  onSuccess: () => void
}) {
  const [outcome, setOutcome] = useState('')
  const [notes, setNotes] = useState('')
  const [finalCharge, setFinalCharge] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit() {
    if (!outcome) { setError('Select an outcome'); return }
    setBusy(true)
    setError('')
    try {
      await adminApi.recordOutcome(caseData.ticket_id, {
        outcome,
        outcome_notes: notes.trim() || undefined,
        final_charge: outcome === 'reduced' ? finalCharge.trim() : undefined,
        attorney_name: caseData.attorney_name,
      })
      await adminApi.logActivity(caseData.case_id, {
        type: 'outcome_logged',
        note: `Outcome recorded: ${outcome}${notes ? ` — ${notes}` : ''}`,
        new_status: 'outcome_logged',
        created_by: reviewer,
        created_by_name: reviewer,
      })
      onSuccess()
    } catch (e: any) {
      setError(e.message || 'Failed to record outcome')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.4)' }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <p className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-0.5">Record Outcome</p>
          <p className="font-semibold" style={{ color: BRAND.ink }}>{caseData.driver_name} — {caseData.violation}</p>
          <p className="text-xs text-gray-400 mt-0.5">Attorney: {caseData.attorney_name}</p>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1.5">Outcome</label>
            <div className="grid grid-cols-3 gap-2">
              {OUTCOMES.map(o => (
                <button key={o}
                  onClick={() => setOutcome(o)}
                  className={`py-2 rounded-lg text-sm capitalize font-medium border transition-colors ${outcome === o ? 'border-transparent text-white' : 'border-gray-200 text-gray-500'}`}
                  style={outcome === o ? { background: o === 'won' || o === 'dismissed' ? BRAND.tealDark : o === 'lost' ? '#DC2626' : BRAND.ink } : {}}>
                  {o}
                </button>
              ))}
            </div>
          </div>

          {outcome === 'reduced' && (
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1.5">Reduced to (final charge)</label>
              <input
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none"
                placeholder="e.g. Non-moving violation, improper equipment"
                value={finalCharge}
                onChange={e => setFinalCharge(e.target.value)}
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-gray-500 mb-1.5">Notes</label>
            <textarea
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none"
              rows={3}
              placeholder="What happened? Any details for the attorney payout record."
              value={notes}
              onChange={e => setNotes(e.target.value)}
            />
          </div>

          {error && <p className="text-red-600 text-sm">{error}</p>}
        </div>

        <div className="px-6 pb-5 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-500 hover:bg-gray-50">
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={busy || !outcome}
            className="px-5 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-40"
            style={{ background: BRAND.ink }}>
            {busy ? 'Saving…' : 'Record Outcome'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Bid countdown timer ───────────────────────────────────────────────────

function BidCountdown({ deadline }: { deadline: string }) {
  const [remaining, setRemaining] = useState('')
  const [expired, setExpired] = useState(false)

  useEffect(() => {
    function tick() {
      const diff = new Date(deadline).getTime() - Date.now()
      if (diff <= 0) { setExpired(true); setRemaining('DEADLINE PASSED'); return }
      const d = Math.floor(diff / 86400000)
      const h = Math.floor((diff % 86400000) / 3600000)
      const m = Math.floor((diff % 3600000) / 60000)
      const s = Math.floor((diff % 60000) / 1000)
      setRemaining(d > 0 ? `${d}d ${h}h ${m}m remaining` : `${h}h ${m}m ${s}s remaining`)
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [deadline])

  return (
    <span className={`text-xs font-bold px-2 py-1 rounded-lg ${expired ? 'bg-red-100 text-red-600' : 'bg-amber-50 text-amber-700'}`}>
      {remaining}
    </span>
  )
}

// ── Add Bid form ──────────────────────────────────────────────────────────

function AddBidForm({ caseId, reviewer, onSaved, onCancel }: {
  caseId: string; reviewer: string; onSaved: () => void; onCancel: () => void
}) {
  const [form, setForm] = useState({
    attorney_name: '', attorney_firm: '', attorney_email: '', attorney_phone: '',
    fee_amount: '', fee_structure: 'flat', fee_includes: '', fee_notes: '',
    timeline_estimate: '', timeline_court_appearances: '', timeline_days_estimate: '',
    outcome_confidence: 'medium',
    outcome_best_case: '', outcome_likely: '', outcome_worst_case: '',
    local_court_experience: 'false', local_court_notes: '',
    similar_cases_count: '', notes: '',
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')
  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.attorney_name) return
    setSaving(true)
    setErr('')
    try {
      await controlApi.submitBid(caseId, {
        ...form,
        fee_amount: form.fee_amount ? parseFloat(form.fee_amount) : null,
        timeline_court_appearances: form.timeline_court_appearances ? parseInt(form.timeline_court_appearances) : null,
        timeline_days_estimate: form.timeline_days_estimate ? parseInt(form.timeline_days_estimate) : null,
        similar_cases_count: form.similar_cases_count ? parseInt(form.similar_cases_count) : null,
        local_court_experience: form.local_court_experience === 'true',
        entered_by: reviewer,
      })
      onSaved()
    } catch (e: any) { setErr(e.message) }
    finally { setSaving(false) }
  }

  const inp = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1'

  return (
    <form onSubmit={submit} className="bg-gray-50 rounded-xl border border-gray-200 p-5 space-y-5">
      <p className="text-xs font-bold uppercase tracking-wide text-gray-400">New Attorney Bid</p>

      {/* Attorney Info */}
      <div>
        <p className="text-xs font-semibold text-gray-500 mb-2">Attorney Info</p>
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="text-xs text-gray-400 mb-0.5 block">Attorney Name *</label>
            <input required value={form.attorney_name} onChange={e => set('attorney_name', e.target.value)}
              className={inp} placeholder="Jane Smith" />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-0.5 block">Firm</label>
            <input value={form.attorney_firm} onChange={e => set('attorney_firm', e.target.value)}
              className={inp} placeholder="Smith Law LLC" />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-0.5 block">Phone</label>
            <input value={form.attorney_phone} onChange={e => set('attorney_phone', e.target.value)}
              className={inp} placeholder="(555) 000-0000" />
          </div>
          <div className="col-span-2">
            <label className="text-xs text-gray-400 mb-0.5 block">Email</label>
            <input type="email" value={form.attorney_email} onChange={e => set('attorney_email', e.target.value)}
              className={inp} placeholder="jane@smithlaw.com" />
          </div>
        </div>
      </div>

      {/* Fee */}
      <div>
        <p className="text-xs font-semibold text-gray-500 mb-2">Fee</p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-400 mb-0.5 block">Amount ($)</label>
            <input type="number" value={form.fee_amount} onChange={e => set('fee_amount', e.target.value)}
              className={inp} placeholder="750" />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-0.5 block">Structure</label>
            <select value={form.fee_structure} onChange={e => set('fee_structure', e.target.value)} className={inp}>
              <option value="flat">Flat fee</option>
              <option value="hourly">Hourly</option>
              <option value="contingency">Contingency</option>
            </select>
          </div>
          <div className="col-span-2">
            <label className="text-xs text-gray-400 mb-0.5 block">What's included</label>
            <input value={form.fee_includes} onChange={e => set('fee_includes', e.target.value)}
              className={inp} placeholder="All court appearances, pre-trial motions, negotiations" />
          </div>
          <div className="col-span-2">
            <label className="text-xs text-gray-400 mb-0.5 block">Fee notes</label>
            <input value={form.fee_notes} onChange={e => set('fee_notes', e.target.value)}
              className={inp} placeholder="e.g. Requires 50% upfront" />
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div>
        <p className="text-xs font-semibold text-gray-500 mb-2">Timeline</p>
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="text-xs text-gray-400 mb-0.5 block">Estimate (free text)</label>
            <input value={form.timeline_estimate} onChange={e => set('timeline_estimate', e.target.value)}
              className={inp} placeholder="2 court dates, motion to suppress, ~60–90 days" />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-0.5 block">Court appearances</label>
            <input type="number" value={form.timeline_court_appearances} onChange={e => set('timeline_court_appearances', e.target.value)}
              className={inp} placeholder="2" />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-0.5 block">Estimated days</label>
            <input type="number" value={form.timeline_days_estimate} onChange={e => set('timeline_days_estimate', e.target.value)}
              className={inp} placeholder="75" />
          </div>
        </div>
      </div>

      {/* Outcome projections */}
      <div>
        <p className="text-xs font-semibold text-gray-500 mb-2">Outcome Projections</p>
        <div className="mb-3">
          <label className="text-xs text-gray-400 mb-1.5 block">Confidence</label>
          <div className="flex gap-2">
            {(['high', 'medium', 'low'] as const).map(c => (
              <button key={c} type="button" onClick={() => set('outcome_confidence', c)}
                className="flex-1 py-1.5 rounded-lg text-xs font-bold capitalize border-2 transition-all"
                style={form.outcome_confidence === c
                  ? { borderColor: c === 'high' ? BRAND.teal : c === 'medium' ? '#F59E0B' : '#EF4444', background: c === 'high' ? BRAND.tealTint : c === 'medium' ? '#FFFBEB' : '#FEF2F2', color: c === 'high' ? BRAND.tealDark : c === 'medium' ? '#92400E' : '#991B1B' }
                  : { borderColor: '#E5E7EB', color: '#9CA3AF' }}>
                {c}
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 gap-2">
          <div>
            <label className="text-xs text-gray-400 mb-0.5 block">🟢 Best case</label>
            <input value={form.outcome_best_case} onChange={e => set('outcome_best_case', e.target.value)}
              className={inp} placeholder="Dismissed / reduced to non-moving" />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-0.5 block">🟡 Likely outcome</label>
            <input value={form.outcome_likely} onChange={e => set('outcome_likely', e.target.value)}
              className={inp} placeholder="Reduced charge, 1 point" />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-0.5 block">🔴 Worst case</label>
            <input value={form.outcome_worst_case} onChange={e => set('outcome_worst_case', e.target.value)}
              className={inp} placeholder="Full conviction, 3 points" />
          </div>
        </div>
      </div>

      {/* Local experience */}
      <div>
        <p className="text-xs font-semibold text-gray-500 mb-2">Local Court Experience</p>
        <div className="flex gap-2 mb-2">
          {[['true', 'Yes — local experience'], ['false', 'No local experience']].map(([v, lbl]) => (
            <button key={v} type="button" onClick={() => set('local_court_experience', v)}
              className="flex-1 py-1.5 rounded-lg text-xs font-semibold border-2 transition-all"
              style={form.local_court_experience === v
                ? { borderColor: BRAND.teal, background: BRAND.tealTint, color: BRAND.tealDark }
                : { borderColor: '#E5E7EB', color: '#9CA3AF' }}>
              {lbl}
            </button>
          ))}
        </div>
        {form.local_court_experience === 'true' && (
          <textarea value={form.local_court_notes} onChange={e => set('local_court_notes', e.target.value)}
            className={`${inp} resize-none`} rows={2}
            placeholder="Judges known, court tendencies, local DA relationships…" />
        )}
        <div className="mt-2">
          <label className="text-xs text-gray-400 mb-0.5 block">Similar CDL cases handled</label>
          <input type="number" value={form.similar_cases_count} onChange={e => set('similar_cases_count', e.target.value)}
            className={inp} placeholder="15" />
        </div>
      </div>

      {/* Notes */}
      <div>
        <label className="text-xs text-gray-400 mb-0.5 block">Additional Notes</label>
        <textarea value={form.notes} onChange={e => set('notes', e.target.value)}
          className={`${inp} resize-none`} rows={2}
          placeholder="Anything else the attorney said, references, availability…" />
      </div>

      {err && <p className="text-red-500 text-xs">{err}</p>}

      <div className="flex gap-2">
        <button type="button" onClick={onCancel}
          className="flex-1 py-2 rounded-lg text-sm border border-gray-200 text-gray-500 hover:bg-gray-50">
          Cancel
        </button>
        <button type="submit" disabled={saving || !form.attorney_name}
          className="flex-1 py-2 rounded-lg text-sm font-bold text-white disabled:opacity-40"
          style={{ background: BRAND.teal }}>
          {saving ? 'Saving…' : 'Save Bid'}
        </button>
      </div>
    </form>
  )
}

// ── Bid card ──────────────────────────────────────────────────────────────

function BidCard({ bid, caseId, reviewer, onUpdate, onToast }: {
  bid: any; caseId: string; reviewer: string; onUpdate: () => void; onToast: (m: string, ok: boolean) => void
}) {
  const [selecting, setSelecting] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const isSelected = bid.bid_status === 'selected'
  const isRejected = bid.bid_status === 'rejected'

  async function handleSelect() {
    if (!confirm(`Select ${bid.attorney_name} for this case?`)) return
    setSelecting(true)
    try {
      await controlApi.selectBid(caseId, bid.bid_id, { selected_by: reviewer })
      onToast(`${bid.attorney_name} selected — case awarded`, true)
      onUpdate()
    } catch (e: any) { onToast(e.message, false) }
    finally { setSelecting(false) }
  }

  async function handleDelete() {
    if (!confirm('Remove this bid?')) return
    setDeleting(true)
    try {
      await controlApi.deleteBid(caseId, bid.bid_id)
      onToast('Bid removed', true)
      onUpdate()
    } catch (e: any) { onToast(e.message, false) }
    finally { setDeleting(false) }
  }

  const confColor = bid.outcome_confidence === 'high' ? { bg: BRAND.tealTint, text: BRAND.tealDark }
    : bid.outcome_confidence === 'low' ? { bg: '#FEF2F2', text: '#991B1B' }
    : { bg: '#FFFBEB', text: '#92400E' }

  return (
    <div className={`rounded-xl border-2 p-4 space-y-3 transition-all ${isSelected ? 'border-teal-400 bg-teal-50' : isRejected ? 'border-gray-100 opacity-50' : 'border-gray-200 bg-white'}`}>
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-bold text-sm" style={{ color: BRAND.ink }}>{bid.attorney_name}</div>
          {bid.attorney_firm && <div className="text-xs text-gray-400">{bid.attorney_firm}</div>}
          <div className="flex gap-3 mt-0.5">
            {bid.attorney_phone && <span className="text-xs text-gray-400">{bid.attorney_phone}</span>}
            {bid.attorney_email && <span className="text-xs text-gray-400">{bid.attorney_email}</span>}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          {isSelected && <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-teal-100 text-teal-700">SELECTED</span>}
          {isRejected && <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-gray-100 text-gray-400">NOT SELECTED</span>}
          {bid.outcome_confidence && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase"
              style={{ background: confColor.bg, color: confColor.text }}>
              {bid.outcome_confidence} confidence
            </span>
          )}
        </div>
      </div>

      {/* Fee + timeline */}
      <div className="grid grid-cols-2 gap-3">
        {bid.fee_amount != null && (
          <div className="bg-gray-50 rounded-lg p-2.5">
            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-0.5">Fee</div>
            <div className="text-lg font-black" style={{ color: BRAND.ink }}>${bid.fee_amount.toLocaleString()}</div>
            <div className="text-[10px] text-gray-400 capitalize">{bid.fee_structure}</div>
            {bid.fee_includes && <div className="text-[10px] text-gray-500 mt-0.5">{bid.fee_includes}</div>}
          </div>
        )}
        {(bid.timeline_estimate || bid.timeline_days_estimate) && (
          <div className="bg-gray-50 rounded-lg p-2.5">
            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-0.5">Timeline</div>
            {bid.timeline_days_estimate && (
              <div className="text-lg font-black" style={{ color: BRAND.ink }}>~{bid.timeline_days_estimate}d</div>
            )}
            {bid.timeline_court_appearances && (
              <div className="text-[10px] text-gray-400">{bid.timeline_court_appearances} court appearance{bid.timeline_court_appearances > 1 ? 's' : ''}</div>
            )}
            {bid.timeline_estimate && <div className="text-[10px] text-gray-500 mt-0.5">{bid.timeline_estimate}</div>}
          </div>
        )}
      </div>

      {/* Outcome projections */}
      {(bid.outcome_best_case || bid.outcome_likely || bid.outcome_worst_case) && (
        <div className="space-y-1">
          <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Projected Outcomes</div>
          {bid.outcome_best_case && (
            <div className="flex gap-2 items-start">
              <span className="text-xs shrink-0">🟢</span>
              <span className="text-xs text-gray-600"><span className="font-semibold text-gray-700">Best:</span> {bid.outcome_best_case}</span>
            </div>
          )}
          {bid.outcome_likely && (
            <div className="flex gap-2 items-start">
              <span className="text-xs shrink-0">🟡</span>
              <span className="text-xs text-gray-600"><span className="font-semibold text-gray-700">Likely:</span> {bid.outcome_likely}</span>
            </div>
          )}
          {bid.outcome_worst_case && (
            <div className="flex gap-2 items-start">
              <span className="text-xs shrink-0">🔴</span>
              <span className="text-xs text-gray-600"><span className="font-semibold text-gray-700">Worst:</span> {bid.outcome_worst_case}</span>
            </div>
          )}
        </div>
      )}

      {/* Local experience */}
      {bid.local_court_experience != null && (
        <div className="text-xs text-gray-500">
          <span className={`font-semibold ${bid.local_court_experience ? 'text-green-600' : 'text-gray-400'}`}>
            {bid.local_court_experience ? '✓ Local court experience' : '✗ No local experience'}
          </span>
          {bid.local_court_notes && <span className="text-gray-400"> — {bid.local_court_notes}</span>}
        </div>
      )}
      {bid.similar_cases_count != null && (
        <div className="text-xs text-gray-400">{bid.similar_cases_count} similar CDL cases handled</div>
      )}
      {bid.notes && <div className="text-xs text-gray-500 bg-gray-50 rounded-lg p-2">{bid.notes}</div>}

      {/* Actions */}
      {!isSelected && !isRejected && (
        <div className="flex gap-2 pt-1">
          <button onClick={handleSelect} disabled={selecting}
            className="flex-1 py-2 rounded-lg text-xs font-bold text-white disabled:opacity-40"
            style={{ background: BRAND.teal }}>
            {selecting ? 'Selecting…' : '✓ Select This Attorney'}
          </button>
          <button onClick={handleDelete} disabled={deleting}
            className="px-3 py-2 rounded-lg text-xs text-red-400 hover:bg-red-50 border border-red-100">
            {deleting ? '…' : 'Remove'}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Similar bids intelligence search ─────────────────────────────────────

function SimilarBidsSearch({ caseData }: { caseData: any }) {
  const [bids, setBids] = useState<any[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)

  async function search() {
    if (bids !== null) { setOpen(o => !o); return }
    setOpen(true)
    setLoading(true)
    try {
      const res = await controlApi.searchBids({
        state: caseData.ticket_state,
        violation: caseData.violation,
      })
      setBids(res.bids ?? [])
    } catch { setBids([]) }
    finally { setLoading(false) }
  }

  const selected = (bids ?? []).filter((b: any) => b.bid_status === 'selected')
  const others   = (bids ?? []).filter((b: any) => b.bid_status !== 'selected' && b.bid_status !== 'removed')

  return (
    <div className="border border-dashed border-gray-200 rounded-xl overflow-hidden">
      <button onClick={search}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-500 hover:bg-gray-50 transition-colors">
        <span>🔍 Past attorney bids for {caseData.ticket_state} · {caseData.violation || 'similar cases'}</span>
        <span className="text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="border-t border-gray-100 p-4">
          {loading && <p className="text-sm text-gray-400 text-center py-4">Searching…</p>}
          {!loading && bids !== null && bids.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">No past bids found for this state + violation. This will be the first.</p>
          )}
          {!loading && bids !== null && bids.length > 0 && (
            <div className="space-y-4">
              {selected.length > 0 && (
                <div>
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-2">Previously Selected Attorneys</p>
                  <div className="space-y-2">
                    {selected.map((b: any) => (
                      <div key={b.bid_id} className="bg-teal-50 border border-teal-200 rounded-lg p-3">
                        <div className="flex justify-between items-start">
                          <div>
                            <div className="text-sm font-bold" style={{ color: BRAND.ink }}>{b.attorney_name}</div>
                            <div className="text-xs text-gray-400">{b.attorney_firm} · {b.ticket_state} · {b.violation_category}</div>
                          </div>
                          <div className="text-right">
                            {b.fee_amount && <div className="text-sm font-bold text-gray-700">${b.fee_amount.toLocaleString()}</div>}
                            {b.actual_outcome && (
                              <div className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${b.actual_outcome === 'won' || b.actual_outcome === 'dismissed' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                                {b.actual_outcome}
                              </div>
                            )}
                          </div>
                        </div>
                        {b.outcome_likely && <div className="text-xs text-gray-500 mt-1">Projected: {b.outcome_likely}</div>}
                        {b.local_court_experience && <div className="text-xs text-green-600 mt-0.5">✓ Local experience</div>}
                        {b.attorney_performance_rating && (
                          <div className="text-xs text-gray-500 mt-0.5">Rating: {'★'.repeat(b.attorney_performance_rating)}{'☆'.repeat(5 - b.attorney_performance_rating)}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {others.length > 0 && (
                <div>
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-2">Other Past Bids</p>
                  <div className="space-y-1">
                    {others.slice(0, 5).map((b: any) => (
                      <div key={b.bid_id} className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-gray-50">
                        <div>
                          <span className="text-sm font-medium text-gray-700">{b.attorney_name}</span>
                          <span className="text-xs text-gray-400 ml-2">{b.attorney_firm}</span>
                        </div>
                        <div className="flex gap-3 items-center text-xs text-gray-400">
                          {b.fee_amount && <span>${b.fee_amount.toLocaleString()}</span>}
                          {b.timeline_days_estimate && <span>~{b.timeline_days_estimate}d</span>}
                          {b.outcome_confidence && <span className="capitalize">{b.outcome_confidence} conf.</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Bids panel (full) ─────────────────────────────────────────────────────

function BidsPanel({ caseData, caseId, reviewer, onRefresh, onToast }: {
  caseData: any; caseId: string; reviewer: string; onRefresh: () => void; onToast: (m: string, ok: boolean) => void
}) {
  const [bids, setBids] = useState<any[]>([])
  const [loadingBids, setLoadingBids] = useState(true)
  const [showAddForm, setShowAddForm] = useState(false)
  const [startingBids, setStartingBids] = useState(false)

  const loadBids = useCallback(() => {
    setLoadingBids(true)
    controlApi.listBids(caseId).then(r => setBids(r.bids ?? [])).catch(() => setBids([])).finally(() => setLoadingBids(false))
  }, [caseId])

  useEffect(() => { loadBids() }, [loadBids])

  async function handleRequestBids() {
    setStartingBids(true)
    try {
      await controlApi.requestBids(caseId, { requested_by: reviewer })
      onToast('Bid window opened — 72 business hours', true)
      onRefresh()
    } catch (e: any) { onToast(e.message, false) }
    finally { setStartingBids(false) }
  }

  const bidDeadline = caseData.bid_deadline
  const bidStatus = caseData.bid_status  // undefined | 'open' | 'awarded'
  const selectedBid = bids.find(b => b.bid_status === 'selected')

  return (
    <div className="space-y-4">
      {/* Bid window status bar */}
      <div className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-3 border border-gray-200">
        <div>
          <div className="text-xs font-bold text-gray-700">
            {!bidStatus && 'Bid process not started'}
            {bidStatus === 'open' && 'Bid window open'}
            {bidStatus === 'awarded' && `Awarded to ${selectedBid?.attorney_name || 'attorney'}`}
          </div>
          {bidDeadline && (
            <div className="text-xs text-gray-400 mt-0.5">Deadline: {new Date(bidDeadline).toLocaleString()}</div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {bidDeadline && <BidCountdown deadline={bidDeadline} />}
          {!bidStatus && (
            <button onClick={handleRequestBids} disabled={startingBids}
              className="px-3 py-1.5 rounded-lg text-xs font-bold text-white disabled:opacity-40"
              style={{ background: BRAND.ink }}>
              {startingBids ? 'Starting…' : 'Start 72hr Bid Window'}
            </button>
          )}
          {bidStatus === 'open' && !showAddForm && (
            <button onClick={() => setShowAddForm(true)}
              className="px-3 py-1.5 rounded-lg text-xs font-bold text-white"
              style={{ background: BRAND.teal }}>
              + Add Bid
            </button>
          )}
        </div>
      </div>

      {/* Add bid form */}
      {showAddForm && (
        <AddBidForm
          caseId={caseId}
          reviewer={reviewer}
          onSaved={() => { setShowAddForm(false); loadBids(); onToast('Bid saved', true) }}
          onCancel={() => setShowAddForm(false)}
        />
      )}

      {/* Allow adding bids even before window is formally opened */}
      {!bidStatus && !showAddForm && (
        <button onClick={() => setShowAddForm(true)}
          className="w-full py-2 rounded-lg text-sm border border-dashed border-gray-300 text-gray-400 hover:border-gray-400 hover:text-gray-500 transition-colors">
          + Manually add bid (without starting timer)
        </button>
      )}

      {/* Bids list */}
      {loadingBids ? (
        <Spinner />
      ) : bids.length === 0 ? (
        <div className="text-center py-6 text-gray-400 text-sm">
          No bids yet. {bidStatus === 'open' ? 'Add bids as attorneys respond.' : 'Start the bid window or add a bid manually.'}
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs font-bold text-gray-400 uppercase tracking-wide">{bids.length} Bid{bids.length > 1 ? 's' : ''} Received</p>
          {bids.map(bid => (
            <BidCard
              key={bid.bid_id}
              bid={bid}
              caseId={caseId}
              reviewer={reviewer}
              onUpdate={loadBids}
              onToast={onToast}
            />
          ))}
        </div>
      )}

      {/* Past bid intelligence */}
      <SimilarBidsSearch caseData={caseData} />
    </div>
  )
}

// ── Case Detail Drawer ────────────────────────────────────────────────────

type DrawerTab = 'bids' | 'activity'

function CaseDrawer({
  caseId,
  reviewer,
  onClose,
  onUpdate,
}: {
  caseId: string
  reviewer: string
  onClose: () => void
  onUpdate: () => void
}) {
  const [caseData, setCaseData] = useState<any>(null)
  const [drawerTab, setDrawerTab] = useState<DrawerTab>('bids')
  const [logNote, setLogNote] = useState('')
  const [logType, setLogType] = useState('note_added')
  const [logStatus, setLogStatus] = useState('')
  const [logBusy, setLogBusy] = useState(false)
  const [showOutcome, setShowOutcome] = useState(false)
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  function showToast(msg: string, ok: boolean) {
    if (timerRef.current) clearTimeout(timerRef.current)
    setToast({ msg, ok })
    timerRef.current = setTimeout(() => setToast(null), 3500)
  }

  const load = useCallback(() => {
    adminApi.getCase(caseId).then(setCaseData).catch(console.error)
  }, [caseId])

  useEffect(() => { load() }, [load])

  async function handleLogActivity() {
    if (!logNote.trim()) return
    setLogBusy(true)
    try {
      await adminApi.logActivity(caseId, {
        type: logType,
        note: logNote.trim(),
        new_status: logStatus || undefined,
        created_by: reviewer,
        created_by_name: reviewer,
      })
      setLogNote('')
      setLogStatus('')
      showToast('Update logged', true)
      load()
      onUpdate()
    } catch (e: any) {
      showToast(e.message || 'Failed', false)
    } finally {
      setLogBusy(false)
    }
  }

  const status = caseData?.status ?? ''
  const nextStatuses = CASE_STATUS_NEXT[status] ?? []

  return (
    <div className="fixed inset-0 z-30 flex" style={{ background: 'rgba(0,0,0,0.3)' }} onClick={onClose}>
      <div className="ml-auto w-full max-w-xl h-full bg-white shadow-2xl overflow-y-auto flex flex-col"
        onClick={e => e.stopPropagation()}>

        {!caseData ? <Spinner /> : (
          <>
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-100 sticky top-0 bg-white z-10">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wide text-gray-400">Case Detail</p>
                  <p className="text-lg font-bold mt-0.5" style={{ color: BRAND.ink }}>{caseData.driver_name}</p>
                  <p className="text-sm text-gray-500">{caseData.violation} · {caseData.ticket_state}{caseData.ticket_county ? ` · ${caseData.ticket_county}` : ''}</p>
                </div>
                <button onClick={onClose} className="text-gray-300 hover:text-gray-500 text-xl leading-none mt-1">✕</button>
              </div>

              <div className="flex items-center gap-2 mt-2 flex-wrap">
                <span className="text-xs px-2 py-0.5 rounded-full font-semibold border border-gray-200 text-gray-600">
                  {CASE_STATUS_LABELS[status] ?? status}
                </span>
                {caseData.attorney_name && (
                  <span className="text-xs text-gray-400">Atty: {caseData.attorney_name}</span>
                )}
                {caseData.court_date && (
                  <span className="text-xs text-gray-400">Court: {caseData.court_date}</span>
                )}
                {status === 'active' && (
                  <button onClick={() => setShowOutcome(true)}
                    className="ml-auto text-xs px-3 py-1.5 rounded-lg font-semibold text-white"
                    style={{ background: BRAND.ink }}>
                    Record Outcome
                  </button>
                )}
              </div>

              {/* Drawer tab bar */}
              <div className="flex gap-1 mt-3 -mb-px">
                {([['bids', 'Bids & Attorney Selection'], ['activity', 'Activity Log']] as [DrawerTab, string][]).map(([t, lbl]) => (
                  <button key={t} onClick={() => setDrawerTab(t)}
                    className="px-4 py-2 text-xs font-semibold border-b-2 transition-colors"
                    style={drawerTab === t
                      ? { borderColor: BRAND.teal, color: BRAND.teal }
                      : { borderColor: 'transparent', color: '#9CA3AF' }}>
                    {lbl}
                    {t === 'bids' && caseData.bid_status === 'open' && (
                      <span className="ml-1.5 w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" />
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* ── Bids tab ── */}
            {drawerTab === 'bids' && (
              <div className="flex-1 px-6 py-4">
                <BidsPanel
                  caseData={caseData}
                  caseId={caseId}
                  reviewer={reviewer}
                  onRefresh={load}
                  onToast={showToast}
                />
              </div>
            )}

            {/* ── Activity tab ── */}
            {drawerTab === 'activity' && (
              <>
                <div className="flex-1 px-6 py-4 space-y-3">
                  <p className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-2">Activity Log</p>
                  {(caseData.activity ?? []).length === 0 && (
                    <p className="text-sm text-gray-400">No activity yet.</p>
                  )}
                  {[...(caseData.activity ?? [])].reverse().map((a: any) => (
                    <div key={a.activity_id} className="flex gap-3">
                      <div className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
                        style={{ background: a.type === 'bid_awarded' ? BRAND.teal : a.type === 'bid_requested' ? '#F59E0B' : BRAND.teal }} />
                      <div>
                        <p className="text-sm" style={{ color: BRAND.ink }}>{a.note}</p>
                        {a.new_status && (
                          <p className="text-xs text-gray-400 mt-0.5">
                            Status → <span className="font-medium">{CASE_STATUS_LABELS[a.new_status] ?? a.new_status}</span>
                          </p>
                        )}
                        <p className="text-xs text-gray-300 mt-0.5">{a.created_by_name} · {a.created_at?.slice(0, 16)?.replace('T', ' ') ?? ''}</p>
                      </div>
                    </div>
                  ))}
                </div>

                {!['closed', 'rejected'].includes(status) && (
                  <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 shrink-0">
                    <p className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-3">Log Update</p>
                    <div className="space-y-2">
                      <div className="flex gap-2">
                        <select className="flex-shrink-0 border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none"
                          value={logType} onChange={e => setLogType(e.target.value)}>
                          <option value="note_added">Note</option>
                          <option value="contacted">Contacted Attorney</option>
                          <option value="attorney_update">Attorney Update</option>
                          <option value="status_change">Status Change</option>
                        </select>
                        {nextStatuses.length > 0 && (
                          <select className="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none"
                            value={logStatus} onChange={e => setLogStatus(e.target.value)}>
                            <option value="">No status change</option>
                            {nextStatuses.filter(s => s.value).map(s => (
                              <option key={s.value} value={s.value}>{s.label}</option>
                            ))}
                          </select>
                        )}
                      </div>
                      <textarea className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none"
                        rows={2} placeholder="What happened? What did the attorney say?"
                        value={logNote} onChange={e => setLogNote(e.target.value)} />
                      <button onClick={handleLogActivity} disabled={logBusy || !logNote.trim()}
                        className="w-full py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-40"
                        style={{ background: BRAND.teal }}>
                        {logBusy ? 'Saving…' : 'Log Update'}
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>

      {showOutcome && caseData && (
        <OutcomeModal
          caseData={caseData}
          reviewer={reviewer}
          onClose={() => setShowOutcome(false)}
          onSuccess={() => { setShowOutcome(false); load(); onUpdate(); showToast('Outcome recorded', true) }}
        />
      )}

      {toast && <Toast msg={toast.msg} ok={toast.ok} onDone={() => setToast(null)} />}
    </div>
  )
}

// ── Main CasesTab export ──────────────────────────────────────────────────

export default function CasesTab({ reviewer }: { reviewer: string }) {
  const [subTab, setSubTab] = useState<'available' | 'active'>('available')
  const [available, setAvailable] = useState<any[] | null>(null)
  const [cases, setCases] = useState<any[] | null>(null)
  const [assignTarget, setAssignTarget] = useState<any | null>(null)
  const [openCaseId, setOpenCaseId] = useState<string | null>(null)
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null)
  const [statusFilter, setStatusFilter] = useState('')

  const loadAvailable = useCallback(() => {
    setAvailable(null)
    adminApi.availableTickets()
      .then(d => setAvailable(d.tickets ?? []))
      .catch(() => setAvailable([]))
  }, [])

  const loadCases = useCallback(() => {
    setCases(null)
    adminApi.listCases(statusFilter || undefined)
      .then(d => setCases(d.cases ?? []))
      .catch(() => setCases([]))
  }, [statusFilter])

  useEffect(() => { if (subTab === 'available') loadAvailable(); else loadCases() }, [subTab, loadAvailable, loadCases])

  const filteredCases = (cases ?? []).filter(c =>
    !statusFilter || c.status === statusFilter
  )

  return (
    <div className="space-y-4">
      {/* Sub-tab toggle */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit">
        {([['available', 'New Tickets'], ['active', 'Active Cases']] as const).map(([val, label]) => (
          <button key={val} onClick={() => setSubTab(val)}
            className={`px-5 py-2 rounded-lg text-sm font-semibold transition-all ${subTab === val ? 'bg-white shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
            style={subTab === val ? { color: BRAND.ink } : {}}>
            {label}
            {val === 'available' && available !== null && available.length > 0 && (
              <span className="ml-1.5 text-[10px] font-bold px-1.5 py-0.5 rounded-full text-white"
                style={{ background: '#DC2626' }}>{available.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* ── New Tickets ── */}
      {subTab === 'available' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {available === null ? <Spinner /> : available.length === 0 ? (
            <div className="py-16 text-center">
              <p className="text-gray-400 text-sm">No tickets awaiting assignment.</p>
              <p className="text-gray-300 text-xs mt-1">Approve tickets from the Review Queue to populate this list.</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['Urgency', 'Driver', 'Violation', 'State / County', 'Court Date', 'Price', 'Action'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {available.map((t: any) => (
                  <tr key={t.ticket_id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3"><UrgencyBadge level={t.urgency_level} /></td>
                    <td className="px-4 py-3">
                      <p className="font-medium text-sm" style={{ color: BRAND.ink }}>{t.driver_name || '—'}</p>
                      <p className="text-xs text-gray-400 font-mono">{t.ticket_id.slice(0, 8)}</p>
                    </td>
                    <td className="px-4 py-3 max-w-[180px]">
                      <p className="text-xs font-medium text-gray-700">{t.violation_category}</p>
                      <p className="text-xs text-gray-400 truncate">{t.violation_description}</p>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600">{t.ticket_state}{t.ticket_county ? ` · ${t.ticket_county}` : ''}</td>
                    <td className="px-4 py-3 text-xs text-gray-600">{t.court_date || '—'}</td>
                    <td className="px-4 py-3 text-xs font-medium" style={{ color: BRAND.tealDark }}>{t.price_display || '—'}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => setAssignTarget(t)}
                        className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white"
                        style={{ background: BRAND.teal }}>
                        Assign
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Active Cases ── */}
      {subTab === 'active' && (
        <div className="space-y-3">
          {/* Status filter */}
          <div className="flex gap-2 flex-wrap">
            {['', 'pending_approval', 'active', 'attorney_declined', 'outcome_logged', 'payout_sent'].map(s => (
              <button key={s} onClick={() => setStatusFilter(s)}
                className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${statusFilter === s ? 'text-white border-transparent' : 'border-gray-200 text-gray-500 hover:border-gray-300'}`}
                style={statusFilter === s ? { background: BRAND.ink } : {}}>
                {s ? (CASE_STATUS_LABELS[s] ?? s) : 'All Open'}
              </button>
            ))}
            <button onClick={loadCases} className="px-3 py-1 rounded-lg text-xs font-medium border border-gray-200 text-gray-400 hover:border-gray-300 ml-auto">
              Refresh
            </button>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            {cases === null ? <Spinner /> : filteredCases.length === 0 ? (
              <div className="py-16 text-center">
                <p className="text-gray-400 text-sm">No cases found.</p>
                <p className="text-gray-300 text-xs mt-1">Assign an attorney to a New Ticket to create a case.</p>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    {['Driver', 'Violation', 'Attorney', 'Status', 'Court Date', 'Assigned', 'Action'].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredCases.map((c: any) => (
                    <tr key={c.case_id} className="hover:bg-gray-50 transition-colors cursor-pointer"
                      onClick={() => setOpenCaseId(c.case_id)}>
                      <td className="px-4 py-3">
                        <p className="font-medium text-sm" style={{ color: BRAND.ink }}>{c.driver_name || '—'}</p>
                        <p className="text-xs text-gray-400">{c.ticket_state}</p>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-600 max-w-[160px] truncate">{c.violation || '—'}</td>
                      <td className="px-4 py-3">
                        <p className="text-xs font-medium text-gray-700">{c.attorney_name || '—'}</p>
                        <p className="text-xs text-gray-400">{c.contact_method}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                          c.status === 'active' ? 'bg-green-100 text-green-700' :
                          c.status === 'attorney_declined' ? 'bg-red-100 text-red-700' :
                          c.status === 'outcome_logged' ? 'bg-blue-100 text-blue-700' :
                          'bg-gray-100 text-gray-500'}`}>
                          {CASE_STATUS_LABELS[c.status] ?? c.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">{c.court_date || '—'}</td>
                      <td className="px-4 py-3 text-xs text-gray-400">
                        {c.assigned_at?.slice(0, 10) ?? '—'}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={e => { e.stopPropagation(); setOpenCaseId(c.case_id) }}
                          className="px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 text-gray-600 hover:bg-gray-50">
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* Assign modal */}
      {assignTarget && (
        <AssignModal
          ticket={assignTarget}
          reviewer={reviewer}
          onClose={() => setAssignTarget(null)}
          onSuccess={() => {
            setAssignTarget(null)
            setToast({ msg: `Attorney assigned — ticket moved to Admin Assigned`, ok: true })
            loadAvailable()
          }}
        />
      )}

      {/* Case detail drawer */}
      {openCaseId && (
        <CaseDrawer
          caseId={openCaseId}
          reviewer={reviewer}
          onClose={() => setOpenCaseId(null)}
          onUpdate={loadCases}
        />
      )}

      {toast && <Toast msg={toast.msg} ok={toast.ok} onDone={() => setToast(null)} />}
    </div>
  )
}
