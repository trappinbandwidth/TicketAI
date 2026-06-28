import { useCallback, useEffect, useState } from 'react'
import { controlApi } from '../api/admin'
import { B, Spinner, Err, Badge, Drawer, Field, FieldGrid, useToast, useStaff } from '../shared/CpComponents'

function CaseDrawer({ caseData, staff, onClose, onRefresh, loadingDetail, show }: {
  caseData: any; staff: string; onClose: () => void; onRefresh: () => void; loadingDetail: boolean; show: (m: string, ok?: boolean) => void
}) {
  const [note, setNote] = useState('')
  const [newStatus, setNewStatus] = useState('')
  const [outcome, setOutcome] = useState('')
  const [outcomeNotes, setOutcomeNotes] = useState('')
  const [feeAmount, setFeeAmount] = useState(caseData.attorney_fee_amount != null ? String(caseData.attorney_fee_amount) : '')
  const [feeNotes, setFeeNotes] = useState(caseData.fee_notes || '')
  const [payoutAmount, setPayoutAmount] = useState(feeAmount)
  const [saving, setSaving] = useState(false)

  const ticket = caseData.ticket ?? {}
  const activity = (caseData.activity ?? []).slice().reverse()
  const STATUSES = ['pending_approval', 'active', 'attorney_declined', 'outcome_logged', 'closed']

  async function logActivity() {
    if (!note.trim()) return
    setSaving(true)
    try {
      await controlApi.logActivity(caseData.case_id, {
        type: newStatus ? 'status_change' : 'note_added',
        note: note.trim(),
        new_status: newStatus || undefined,
        created_by: staff,
        created_by_name: staff,
      })
      setNote(''); setNewStatus('')
      show('Note logged')
      onRefresh()
    } catch (e: any) { show(e.message, false) }
    finally { setSaving(false) }
  }

  async function recordOutcome() {
    if (!outcome) return
    setSaving(true)
    try {
      await controlApi.recordOutcome(caseData.ticket_id, {
        outcome, outcome_notes: outcomeNotes,
        attorney_id: caseData.attorney_id, attorney_name: caseData.attorney_name,
      })
      await controlApi.logActivity(caseData.case_id, {
        type: 'outcome_logged',
        note: `Outcome: ${outcome}. ${outcomeNotes}`.trim(),
        new_status: 'outcome_logged',
        created_by: staff, created_by_name: staff,
      })
      show('Outcome recorded')
      onRefresh()
    } catch (e: any) { show(e.message, false) }
    finally { setSaving(false) }
  }

  async function saveFees() {
    if (!feeAmount) return
    setSaving(true)
    try {
      await controlApi.updateFees(caseData.case_id, {
        attorney_fee_amount: parseFloat(feeAmount), fee_notes: feeNotes, updated_by: staff,
      })
      show('Fees updated')
      onRefresh()
    } catch (e: any) { show(e.message, false) }
    finally { setSaving(false) }
  }

  async function sendPayout() {
    if (!payoutAmount) return
    if (!confirm(`Send payout of $${payoutAmount} to ${caseData.attorney_name}?`)) return
    setSaving(true)
    try {
      await controlApi.recordPayout(caseData.case_id, {
        payout_amount: parseFloat(payoutAmount), payout_method: 'bank_transfer', paid_by: staff,
      })
      show('Payout recorded')
      onRefresh()
    } catch (e: any) { show(e.message, false) }
    finally { setSaving(false) }
  }

  return (
    <Drawer title={`Case — ${caseData.driver_name || caseData.case_id}`} onClose={onClose}>
      {loadingDetail ? <Spinner /> : (
        <div className="space-y-6">
          <section className="flex items-start gap-4">
            <div className="flex-1">
              <FieldGrid>
                <Field label="Driver" value={caseData.driver_name} />
                <Field label="Attorney" value={caseData.attorney_name} />
                <Field label="Violation" value={caseData.violation} />
                <Field label="State" value={caseData.ticket_state} />
                <Field label="Court Date" value={caseData.court_date} />
                <div>
                  <dt className="text-xs font-medium text-gray-400 uppercase tracking-wide">Status</dt>
                  <dd className="mt-0.5"><Badge status={caseData.status} /></dd>
                </div>
                {caseData.outcome && <Field label="Outcome" value={caseData.outcome.replace(/_/g, ' ')} />}
                {caseData.payout_sent && <Field label="Payout Sent" value={`$${caseData.payout_amount}`} />}
              </FieldGrid>
            </div>
          </section>

          {Object.keys(ticket).length > 0 && (
            <section>
              <h3 className="text-sm font-bold text-gray-700 mb-3">Ticket Details</h3>
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <FieldGrid>
                  <Field label="Citation #" value={ticket.citation_number} />
                  <Field label="Date" value={ticket.date_of_ticket} />
                  <Field label="Category" value={ticket.violation_category} />
                  <Field label="County" value={ticket.ticket_county} />
                  <Field label="CDL #" value={ticket.driver_cdl} />
                  <Field label="Pass Status" value={ticket.pass_status} />
                  <Field label="Price" value={ticket.price_display} />
                  <Field label="AI Scan" value={ticket.pass_status} />
                </FieldGrid>
                {ticket.violation_description && (
                  <p className="text-xs text-gray-500 mt-2">{ticket.violation_description}</p>
                )}
              </div>
            </section>
          )}

          <section>
            <h3 className="text-sm font-bold text-gray-700 mb-3">Log Activity</h3>
            <div className="space-y-3">
              <textarea
                value={note} onChange={e => setNote(e.target.value)}
                placeholder="Enter a note, update, or court outcome…"
                rows={3}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2"
                style={{ '--tw-ring-color': B.teal } as any}
              />
              <div className="flex gap-2 items-center">
                <select value={newStatus} onChange={e => setNewStatus(e.target.value)}
                  className="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1">
                  <option value="">Note only (no status change)</option>
                  {STATUSES.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
                </select>
                <button onClick={logActivity} disabled={saving || !note.trim()}
                  className="px-4 py-2 rounded-lg text-sm font-bold text-white transition-colors shrink-0"
                  style={{ background: saving || !note.trim() ? '#94A3B8' : B.teal }}>
                  {saving ? '…' : 'Log'}
                </button>
              </div>
            </div>
          </section>

          {caseData.status !== 'outcome_logged' && caseData.status !== 'payout_sent' && caseData.status !== 'closed' && (
            <section>
              <h3 className="text-sm font-bold text-gray-700 mb-3">Record Outcome</h3>
              <div className="space-y-3">
                <div className="flex gap-2 flex-wrap">
                  {(['won', 'dismissed', 'reduced', 'lost', 'transferred'] as const).map(o => (
                    <button key={o} type="button" onClick={() => setOutcome(o)}
                      className="px-3 py-1.5 rounded-lg text-xs font-bold capitalize border-2 transition-all"
                      style={outcome === o
                        ? { borderColor: B.teal, background: B.tealTint, color: B.tealDark }
                        : { borderColor: '#E5E7EB', color: '#6B7280' }}>
                      {o}
                    </button>
                  ))}
                </div>
                <textarea
                  value={outcomeNotes} onChange={e => setOutcomeNotes(e.target.value)}
                  placeholder="Outcome notes (charge reduced to, points avoided, etc.)"
                  rows={2} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none" />
                <button onClick={recordOutcome} disabled={saving || !outcome}
                  className="w-full py-2 rounded-lg text-sm font-bold text-white"
                  style={{ background: saving || !outcome ? '#94A3B8' : '#7C3AED' }}>
                  Record Outcome
                </button>
              </div>
            </section>
          )}

          <section>
            <h3 className="text-sm font-bold text-gray-700 mb-3">Attorney Fees</h3>
            <div className="space-y-2">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <span className="absolute left-3 top-2.5 text-sm text-gray-400">$</span>
                  <input type="number" value={feeAmount} onChange={e => setFeeAmount(e.target.value)}
                    placeholder="0.00" className="w-full border border-gray-200 rounded-lg pl-7 pr-3 py-2 text-sm" />
                </div>
                <button onClick={saveFees} disabled={saving || !feeAmount}
                  className="px-4 py-2 rounded-lg text-sm font-bold text-white"
                  style={{ background: saving ? '#94A3B8' : B.ink }}>
                  Save
                </button>
              </div>
              <input value={feeNotes} onChange={e => setFeeNotes(e.target.value)}
                placeholder="Fee notes (e.g. $750 flat fee agreed)"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
            </div>
          </section>

          {(caseData.status === 'outcome_logged' || caseData.status === 'payout_sent') && (
            <section>
              <h3 className="text-sm font-bold text-gray-700 mb-3">Attorney Payout</h3>
              {caseData.payout_sent ? (
                <div className="p-3 rounded-lg text-sm font-medium" style={{ background: B.tealTint, color: B.tealDark }}>
                  Payout of ${caseData.payout_amount} sent by {caseData.payout_sent_by}
                </div>
              ) : (
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <span className="absolute left-3 top-2.5 text-sm text-gray-400">$</span>
                    <input type="number" value={payoutAmount} onChange={e => setPayoutAmount(e.target.value)}
                      placeholder="0.00" className="w-full border border-gray-200 rounded-lg pl-7 pr-3 py-2 text-sm" />
                  </div>
                  <button onClick={sendPayout} disabled={saving || !payoutAmount}
                    className="px-4 py-2 rounded-lg text-sm font-bold text-white"
                    style={{ background: saving ? '#94A3B8' : '#7C3AED' }}>
                    Send Payout
                  </button>
                </div>
              )}
            </section>
          )}

          <section>
            <h3 className="text-sm font-bold text-gray-700 mb-3">Activity ({activity.length})</h3>
            {activity.length === 0 ? (
              <p className="text-sm text-gray-400">No activity yet</p>
            ) : (
              <div className="space-y-3">
                {activity.map((a: any) => (
                  <div key={a.activity_id} className="flex gap-3">
                    <div className="w-2 h-2 rounded-full mt-1.5 shrink-0"
                      style={{ background: a.type === 'outcome_logged' ? '#7C3AED' : a.type === 'payout_created' ? B.teal : B.ink }} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold text-gray-700 capitalize">{a.type?.replace(/_/g, ' ')}</span>
                        {a.new_status && <span className="text-xs text-gray-400">→ <Badge status={a.new_status} /></span>}
                        <span className="text-xs text-gray-400">{a.created_by_name}</span>
                        {a.created_at && (
                          <span className="text-xs text-gray-300">{new Date(a.created_at).toLocaleString()}</span>
                        )}
                      </div>
                      <p className="text-sm text-gray-600 mt-0.5">{a.note}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </Drawer>
  )
}

export default function CpCasesTab() {
  const { staff } = useStaff()
  const [cases, setCases] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [filter, setFilter] = useState('all')
  const [selected, setSelected] = useState<any>(null)
  const [caseDetail, setCaseDetail] = useState<any>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const { show, el: toastEl } = useToast()

  const load = useCallback(() => {
    setLoading(true)
    controlApi.listCases().then(r => setCases(r.cases ?? [])).catch(e => setErr(e.message)).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const openCase = useCallback(async (c: any) => {
    setSelected(c)
    setLoadingDetail(true)
    try {
      const detail = await controlApi.getCase(c.case_id)
      setCaseDetail(detail)
    } catch { setCaseDetail(c) }
    setLoadingDetail(false)
  }, [])

  const refreshCase = useCallback(async () => {
    if (!selected) return
    try { const detail = await controlApi.getCase(selected.case_id); setCaseDetail(detail); load() }
    catch {}
  }, [selected, load])

  const STATUS_FILTERS = ['all', 'pending_approval', 'active', 'outcome_logged', 'payout_sent', 'closed', 'attorney_declined']
  const filtered = cases.filter(c => filter === 'all' || c.status === filter)

  return (
    <div>
      {toastEl}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {STATUS_FILTERS.map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all"
            style={filter === f
              ? { background: B.ink, color: B.teal }
              : { background: '#F1F5F9', color: '#6B7280' }}>
            {f === 'all' ? 'All Cases' : f.replace(/_/g, ' ')}
            {f !== 'all' && ` (${cases.filter(c => c.status === f).length})`}
          </button>
        ))}
      </div>

      {loading && <Spinner />}
      {err && <Err msg={err} />}
      {!loading && !err && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: B.offWhite }}>
                {['Driver', 'Violation', 'State', 'Court Date', 'Attorney', 'Status', 'Fee', ''].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">No cases</td></tr>
              )}
              {filtered.map(c => (
                <tr key={c.case_id} className="border-t border-gray-100 hover:bg-gray-50 cursor-pointer"
                  onClick={() => openCase(c)}>
                  <td className="px-4 py-3 font-medium text-gray-800">{c.driver_name || '—'}</td>
                  <td className="px-4 py-3 text-gray-600 max-w-[160px] truncate">{c.violation || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{c.ticket_state || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {c.court_date ? (
                      <span className={new Date(c.court_date) < new Date() ? 'text-red-500 font-medium' : ''}>
                        {c.court_date}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{c.attorney_name || '—'}</td>
                  <td className="px-4 py-3"><Badge status={c.status} /></td>
                  <td className="px-4 py-3 text-gray-600">
                    {c.attorney_fee_amount != null ? `$${c.attorney_fee_amount.toLocaleString()}` : '—'}
                  </td>
                  <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                    <button onClick={() => openCase(c)}
                      className="text-xs px-2.5 py-1 rounded-lg bg-blue-50 text-blue-600 font-medium hover:bg-blue-100">
                      Manage
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && caseDetail && (
        <CaseDrawer
          caseData={caseDetail}
          staff={staff}
          onClose={() => { setSelected(null); setCaseDetail(null) }}
          onRefresh={refreshCase}
          loadingDetail={loadingDetail}
          show={show}
        />
      )}
    </div>
  )
}
