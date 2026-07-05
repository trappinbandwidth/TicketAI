import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../api/admin'
import { B, Spinner, Err, Badge, useToast } from '../shared/CpComponents'
import type { Reviewer } from '../shared/brandTokens'

const STATUS_FILTERS = ['all', 'submitted', 'interview_scheduled', 'approved', 'rejected'] as const

export default function AttorneyApplicationsTab({ reviewer }: { reviewer: Reviewer }) {
  const [apps, setApps] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [filter, setFilter] = useState<string>('submitted')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [rejecting, setRejecting] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const { show, el: toastEl } = useToast()

  const load = useCallback(() => {
    setLoading(true)
    setErr('')
    const status = filter === 'all' ? undefined : filter
    adminApi.listApplications(status)
      .then((r: any) => setApps(r.applications ?? []))
      .catch((e: any) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [filter])

  useEffect(() => { load() }, [load])

  async function handleInterview(appId: string) {
    setBusy(appId)
    try {
      await adminApi.interviewComplete(appId)
      show('Interview marked complete')
      load()
    } catch (e: any) { show(e.message, false) }
    finally { setBusy(null) }
  }

  async function handleApprove(appId: string) {
    setBusy(appId)
    try {
      await adminApi.approveApplication(appId, reviewer)
      show('Application approved — Firebase Auth account provisioned')
      load()
    } catch (e: any) { show(e.message, false) }
    finally { setBusy(null) }
  }

  async function handleReject(appId: string) {
    if (!rejectReason.trim()) { show('Enter a rejection reason', false); return }
    setBusy(appId)
    try {
      await adminApi.rejectApplication(appId, rejectReason.trim())
      show('Application rejected')
      setRejecting(null)
      setRejectReason('')
      load()
    } catch (e: any) { show(e.message, false) }
    finally { setBusy(null) }
  }

  const TIER_COLOR: Record<string, string> = {
    senior: 'bg-indigo-100 text-indigo-700',
    junior: 'bg-blue-100 text-blue-700',
    law_student: 'bg-gray-100 text-gray-600',
  }

  return (
    <div>
      {toastEl}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold" style={{ color: B.ink }}>Attorney Applications</h2>
          <p className="text-sm text-gray-400 mt-0.5">Review and provision incoming attorney applications</p>
        </div>
        <div className="flex gap-2">
          {STATUS_FILTERS.map(s => (
            <button key={s} onClick={() => setFilter(s)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all"
              style={filter === s
                ? { background: B.teal, color: '#fff' }
                : { background: '#F1F5F9', color: '#64748B' }}>
              {s === 'all' ? 'All' : s.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {loading && <Spinner />}
      {err && <Err msg={err} />}
      {!loading && !err && apps.length === 0 && (
        <div className="text-center py-20 text-gray-400">
          <div className="text-4xl mb-3">📋</div>
          <p className="font-medium">No applications in this status</p>
        </div>
      )}

      {!loading && !err && (
        <div className="space-y-3">
          {apps.map((app: any) => {
            const isOpen = expanded === app.application_id
            const needsInterview = ['junior', 'law_student'].includes(app.tier_requested) && !app.interview_complete
            const canApprove = !needsInterview && app.status !== 'approved' && app.status !== 'rejected'

            return (
              <div key={app.application_id}
                className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div
                  className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => setExpanded(isOpen ? null : app.application_id)}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 flex-wrap">
                      <span className="font-semibold text-sm" style={{ color: B.ink }}>
                        {app.full_name}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TIER_COLOR[app.tier_requested] ?? 'bg-gray-100 text-gray-600'}`}>
                        {app.tier_requested}
                      </span>
                      <Badge status={app.status} />
                      {needsInterview && (
                        <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-amber-100 text-amber-700">
                          Interview required
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-400 mt-1 flex gap-3 flex-wrap">
                      <span>{app.email}</span>
                      {app.phone && <span>{app.phone}</span>}
                      {app.bar_state && <span>Bar: {app.bar_state}</span>}
                      {app.firm_name && <span>{app.firm_name}</span>}
                      <span>Applied {app.submitted_at ? new Date(app.submitted_at).toLocaleDateString() : '—'}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {app.status === 'submitted' && needsInterview && (
                      <button
                        onClick={e => { e.stopPropagation(); handleInterview(app.application_id) }}
                        disabled={busy === app.application_id}
                        className="text-xs px-3 py-1.5 rounded-lg font-semibold bg-blue-50 text-blue-600 hover:bg-blue-100 disabled:opacity-50">
                        {busy === app.application_id ? '…' : 'Mark Interviewed'}
                      </button>
                    )}
                    {canApprove && (
                      <button
                        onClick={e => { e.stopPropagation(); handleApprove(app.application_id) }}
                        disabled={busy === app.application_id}
                        className="text-xs px-3 py-1.5 rounded-lg font-semibold text-white disabled:opacity-50"
                        style={{ background: B.teal }}>
                        {busy === app.application_id ? '…' : 'Approve'}
                      </button>
                    )}
                    {app.status !== 'approved' && app.status !== 'rejected' && rejecting !== app.application_id && (
                      <button
                        onClick={e => { e.stopPropagation(); setRejecting(app.application_id); setRejectReason('') }}
                        className="text-xs px-3 py-1.5 rounded-lg font-semibold bg-red-50 text-red-500 hover:bg-red-100">
                        Reject
                      </button>
                    )}
                    <span className="text-gray-300 text-sm">{isOpen ? '▲' : '▼'}</span>
                  </div>
                </div>

                {/* Reject inline form */}
                {rejecting === app.application_id && (
                  <div className="px-5 pb-4 flex items-center gap-3 border-t border-gray-100 pt-3 bg-red-50">
                    <input
                      value={rejectReason}
                      onChange={e => setRejectReason(e.target.value)}
                      placeholder="Rejection reason…"
                      className="flex-1 border border-red-200 rounded-lg px-3 py-2 text-sm focus:outline-none"
                      onClick={e => e.stopPropagation()}
                    />
                    <button
                      onClick={e => { e.stopPropagation(); handleReject(app.application_id) }}
                      disabled={busy === app.application_id}
                      className="text-xs px-3 py-2 rounded-lg font-semibold bg-red-500 text-white hover:bg-red-600 disabled:opacity-50">
                      {busy === app.application_id ? '…' : 'Confirm Reject'}
                    </button>
                    <button
                      onClick={e => { e.stopPropagation(); setRejecting(null) }}
                      className="text-xs px-3 py-2 rounded-lg font-semibold bg-white border border-gray-200 text-gray-500">
                      Cancel
                    </button>
                  </div>
                )}

                {/* Expanded detail */}
                {isOpen && (
                  <div className="border-t border-gray-100 px-5 py-4 bg-gray-50 grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                    {[
                      ['Bar Number', app.bar_number],
                      ['States Licensed', (app.states_licensed ?? []).join(', ') || '—'],
                      ['Counties', (app.counties_covered ?? []).join(', ') || '—'],
                      ['Years Experience', app.years_experience],
                      ['Referral Source', app.referral_source],
                      ['Interview Complete', app.interview_complete ? 'Yes' : 'No'],
                      ['Approved By', app.approved_by],
                      ['Rejection Reason', app.rejection_reason],
                    ].map(([label, val]) => val ? (
                      <div key={String(label)}>
                        <div className="text-xs text-gray-400 font-medium uppercase tracking-wide mb-0.5">{label}</div>
                        <div className="text-gray-700">{String(val)}</div>
                      </div>
                    ) : null)}
                    {app.resume_url && (
                      <div className="col-span-full flex gap-3">
                        {app.resume_url && <a href={app.resume_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 underline">Resume</a>}
                        {app.bar_license_doc_url && <a href={app.bar_license_doc_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 underline">Bar License</a>}
                        {app.malpractice_insurance_doc_url && <a href={app.malpractice_insurance_doc_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 underline">Malpractice Insurance</a>}
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
