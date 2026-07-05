import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../api/admin'
import { B, Spinner, Err, useToast } from '../shared/CpComponents'
import type { Reviewer } from '../shared/brandTokens'

export default function PendingClaimsTab({ reviewer }: { reviewer: Reviewer }) {
  const [claims, setClaims] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [rejecting, setRejecting] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const { show, el: toastEl } = useToast()

  const load = useCallback(() => {
    setLoading(true)
    setErr('')
    adminApi.pendingClaims()
      .then((r: any) => setClaims(r.claims ?? []))
      .catch((e: any) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  async function handleApprove(ticketId: string) {
    setBusy(ticketId)
    try {
      await adminApi.approveClaim(ticketId, reviewer)
      show('Claim approved — attorney notified')
      setClaims(prev => prev.filter(c => c.ticket_id !== ticketId))
    } catch (e: any) { show(e.message, false) }
    finally { setBusy(null) }
  }

  async function handleReject(ticketId: string) {
    if (!rejectReason.trim()) { show('Enter a rejection reason', false); return }
    setBusy(ticketId)
    try {
      await adminApi.rejectClaim(ticketId, rejectReason.trim(), reviewer)
      show('Claim rejected — attorney notified')
      setClaims(prev => prev.filter(c => c.ticket_id !== ticketId))
      setRejecting(null)
      setRejectReason('')
    } catch (e: any) { show(e.message, false) }
    finally { setBusy(null) }
  }

  return (
    <div>
      {toastEl}
      <div className="mb-6">
        <h2 className="text-lg font-bold" style={{ color: B.ink }}>Pending Claim Approvals</h2>
        <p className="text-sm text-gray-400 mt-0.5">
          Attorneys who claimed a case but require AM approval before it's confirmed
        </p>
      </div>

      {loading && <Spinner />}
      {err && <Err msg={err} />}
      {!loading && !err && claims.length === 0 && (
        <div className="text-center py-20 text-gray-400">
          <div className="text-4xl mb-3">✅</div>
          <p className="font-medium">No pending claims</p>
          <p className="text-sm mt-1">All attorney claims are either approved or auto-assigned</p>
        </div>
      )}

      {!loading && !err && claims.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: B.offWhite }}>
                {['Ticket / Violation', 'State', 'Court Date', 'Claiming Attorney', 'Claimed At', 'Actions'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {claims.map((c: any) => (
                <>
                  <tr key={c.ticket_id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-800">{c.violation_category || c.violation_description || '—'}</div>
                      <div className="text-xs text-gray-400 font-mono mt-0.5">{c.ticket_id}</div>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{c.ticket_state || '—'}</td>
                    <td className="px-4 py-3 text-gray-600">{c.court_date || '—'}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-800">{c.claimed_by_name || c.claimed_by || '—'}</div>
                      {c.claim_note && <div className="text-xs text-gray-400 mt-0.5 italic">"{c.claim_note}"</div>}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {c.claimed_at ? new Date(c.claimed_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleApprove(c.ticket_id)}
                          disabled={busy === c.ticket_id}
                          className="text-xs px-3 py-1.5 rounded-lg font-semibold text-white disabled:opacity-50"
                          style={{ background: B.teal }}>
                          {busy === c.ticket_id ? '…' : 'Approve'}
                        </button>
                        {rejecting !== c.ticket_id && (
                          <button
                            onClick={() => { setRejecting(c.ticket_id); setRejectReason('') }}
                            className="text-xs px-3 py-1.5 rounded-lg font-semibold bg-red-50 text-red-500 hover:bg-red-100">
                            Reject
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {rejecting === c.ticket_id && (
                    <tr className="border-t border-red-100 bg-red-50">
                      <td colSpan={6} className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <input
                            value={rejectReason}
                            onChange={e => setRejectReason(e.target.value)}
                            placeholder="Rejection reason…"
                            className="flex-1 border border-red-200 rounded-lg px-3 py-2 text-sm focus:outline-none"
                          />
                          <button
                            onClick={() => handleReject(c.ticket_id)}
                            disabled={busy === c.ticket_id}
                            className="text-xs px-3 py-2 rounded-lg font-semibold bg-red-500 text-white hover:bg-red-600 disabled:opacity-50">
                            {busy === c.ticket_id ? '…' : 'Confirm Reject'}
                          </button>
                          <button
                            onClick={() => setRejecting(null)}
                            className="text-xs px-3 py-2 rounded-lg font-semibold bg-white border border-gray-200 text-gray-500">
                            Cancel
                          </button>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
