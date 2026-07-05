import { useEffect, useState } from 'react'
import { carrierCrmApi } from '../api/admin'

// ── Types ──────────────────────────────────────────────────────────────────────

interface Carrier {
  dot_number: string
  legal_name: string
  dba_name: string
  phone: string
  email: string
  website: string
  address: string
  city: string
  state: string
  zip_code: string
  driver_total: number
  nbr_power_unit: number
  carrier_operation: string
  hm_flag: string
  pc_flag: string
  mcs150_date: string
  google_rating: string
  google_review_count: string
  google_verified_address: string
  oos_active: boolean
  oos_date: string
  oos_reason: string
  violation_count: number
  status: string
  assigned_to: string
  contacted_at: string | null
  outreach_notes: string
  follow_up_at: string | null
  enrolled_at: string | null
  monthly_rate: string
  driver_count_enrolled: number
  billing_contact: string
  billing_email: string
}

interface Pipeline {
  total: number
  oos_flagged: number
  total_driver_pool: number
  enrolled_drivers: number
  by_status: Record<string, number>
  by_state: Record<string, number>
}

interface CoverageRow {
  state: string
  total: number
  leads: number
  enrolled: number
  driver_pool: number
}

interface JobRun {
  run_id: string
  job: string
  run_at: string
  carriers_fetched?: number
  carriers_written?: number
  carriers_skipped?: number
  oos_updated?: number
  single_state?: string
  status: string
}

// ── Constants ─────────────────────────────────────────────────────────────────

const STATUSES = ['lead', 'contacted', 'demo_scheduled', 'enrolled', 'declined']
const STATUS_COLORS: Record<string, string> = {
  lead:           'bg-gray-700 text-gray-300',
  contacted:      'bg-blue-900 text-blue-300',
  demo_scheduled: 'bg-yellow-900 text-yellow-300',
  enrolled:       'bg-green-900 text-green-300',
  declined:       'bg-red-900 text-red-300',
}
const ASSIGNEES = ['', 'eniola', 'quest', 'justin']

// ── Email template generator ───────────────────────────────────────────────────

function generateEmail(carrier: Carrier): string {
  const name = carrier.dba_name || carrier.legal_name
  const drivers = carrier.driver_total
  const state = carrier.state
  return `Subject: Legal Protection for Your ${drivers}-Driver Fleet — Rig Resolve

Hi ${name} Team,

I'm reaching out because your fleet of ${drivers} CDL drivers in ${state} could be at significant risk every time one of your drivers gets a citation on the road.

A single moving violation can cost a CDL driver their license — and your company a driver. Rig Resolve provides immediate attorney representation for traffic citations, so your drivers are protected from the moment they're pulled over.

Here's what we offer:
• Monthly subscription per driver — no per-ticket fees
• Immediate attorney connection when a ticket is received
• CDL-specialist attorneys who understand commercial violations
• Dashboard visibility for fleet managers to track cases

Carriers with ${drivers}+ drivers typically see a 40% reduction in license suspensions within the first 6 months.

I'd love to schedule a 15-minute call to show you how it works. Are you available this week?

Best,
[Your Name]
Rig Resolve | Protecting CDL Drivers Nationwide
quest@puklabs.com`
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function CarrierNetworkTab() {
  const [pipeline, setPipeline] = useState<Pipeline | null>(null)
  const [carriers, setCarriers] = useState<Carrier[]>([])
  const [coverage, setCoverage] = useState<CoverageRow[]>([])
  const [jobRuns, setJobRuns] = useState<JobRun[]>([])
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState<'list' | 'map'>('list')
  const [filterStatus, setFilterStatus] = useState('')
  const [filterState, setFilterState] = useState('')
  const [filterAssignee, setFilterAssignee] = useState('')
  const [oosOnly, setOosOnly] = useState(false)
  const [selected, setSelected] = useState<Carrier | null>(null)
  const [saving, setSaving] = useState(false)
  const [showEmail, setShowEmail] = useState(false)
  const [emailCopied, setEmailCopied] = useState(false)
  // Edit state
  const [editStatus, setEditStatus] = useState('')
  const [editAssignee, setEditAssignee] = useState('')
  const [editNotes, setEditNotes] = useState('')
  const [editFollowUp, setEditFollowUp] = useState('')
  const [editMonthlyRate, setEditMonthlyRate] = useState('')
  const [editDriversEnrolled, setEditDriversEnrolled] = useState('')
  const [editBillingContact, setEditBillingContact] = useState('')
  const [editBillingEmail, setEditBillingEmail] = useState('')

  const loadData = async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = { limit: 200 }
      if (filterStatus) params.status = filterStatus
      if (filterState) params.state = filterState
      if (filterAssignee) params.assigned_to = filterAssignee
      if (oosOnly) params.oos_only = true

      const [pl, cl, cv, jr] = await Promise.all([
        carrierCrmApi.pipeline(),
        carrierCrmApi.list(params as Parameters<typeof carrierCrmApi.list>[0]),
        carrierCrmApi.coverage(),
        carrierCrmApi.jobHistory(5),
      ])
      setPipeline(pl)
      setCarriers(cl.carriers || [])
      setCoverage(cv.coverage || [])
      setJobRuns(jr.runs || [])
    } catch (e) {
      console.error('CarrierNetworkTab load error:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [filterStatus, filterState, filterAssignee, oosOnly])

  const openDetail = (c: Carrier) => {
    setSelected(c)
    setEditStatus(c.status || 'lead')
    setEditAssignee(c.assigned_to || '')
    setEditNotes(c.outreach_notes || '')
    setEditFollowUp(c.follow_up_at || '')
    setEditMonthlyRate(c.monthly_rate || '')
    setEditDriversEnrolled(c.driver_count_enrolled ? String(c.driver_count_enrolled) : '')
    setEditBillingContact(c.billing_contact || '')
    setEditBillingEmail(c.billing_email || '')
    setShowEmail(false)
  }

  const saveChanges = async () => {
    if (!selected) return
    setSaving(true)
    try {
      await carrierCrmApi.updateOutreach(selected.dot_number, {
        status: editStatus,
        assigned_to: editAssignee,
        outreach_notes: editNotes,
        follow_up_at: editFollowUp || undefined,
      })
      if (editMonthlyRate || editDriversEnrolled || editBillingContact || editBillingEmail) {
        await carrierCrmApi.updateEnrollment(selected.dot_number, {
          monthly_rate: editMonthlyRate || undefined,
          driver_count_enrolled: editDriversEnrolled ? parseInt(editDriversEnrolled) : undefined,
          billing_contact: editBillingContact || undefined,
          billing_email: editBillingEmail || undefined,
        })
      }
      await loadData()
      setSelected(null)
    } catch (e) {
      console.error('Save error:', e)
    } finally {
      setSaving(false)
    }
  }

  const copyEmail = () => {
    if (!selected) return
    navigator.clipboard.writeText(generateEmail(selected))
    setEmailCopied(true)
    setTimeout(() => setEmailCopied(false), 2000)
  }

  const mailtoLink = (c: Carrier) => {
    const subject = encodeURIComponent(`Legal Protection for Your ${c.driver_total}-Driver Fleet — Rig Resolve`)
    return `mailto:${c.email}?subject=${subject}&body=${encodeURIComponent(generateEmail(c))}`
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-400">
      Loading carrier data...
    </div>
  )

  return (
    <div className="space-y-6">

      {/* Pipeline chips */}
      <div className="flex flex-wrap gap-3">
        {STATUSES.map(s => (
          <button
            key={s}
            onClick={() => setFilterStatus(filterStatus === s ? '' : s)}
            className={`px-4 py-2 rounded-full text-sm font-medium border transition-all ${
              filterStatus === s
                ? STATUS_COLORS[s] + ' border-transparent'
                : 'bg-gray-800 text-gray-400 border-gray-700 hover:border-gray-500'
            }`}
          >
            {s.replace('_', ' ')}
            {pipeline?.by_status[s] != null && (
              <span className="ml-2 opacity-70">{pipeline.by_status[s]}</span>
            )}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-3 text-sm text-gray-400">
          <span>🏢 {pipeline?.total?.toLocaleString() ?? 0} carriers</span>
          <span>👤 {pipeline?.total_driver_pool?.toLocaleString() ?? 0} drivers</span>
          <span className="text-green-400">✓ {pipeline?.enrolled_drivers?.toLocaleString() ?? 0} enrolled</span>
          {(pipeline?.oos_flagged ?? 0) > 0 && (
            <span className="text-red-400">⚠ {pipeline?.oos_flagged} OOS</span>
          )}
        </div>
      </div>

      {/* Filters + view toggle */}
      <div className="flex flex-wrap gap-3 items-center">
        <input
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white w-16 uppercase"
          placeholder="State"
          maxLength={2}
          value={filterState}
          onChange={e => setFilterState(e.target.value.toUpperCase())}
        />
        <select
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white"
          value={filterAssignee}
          onChange={e => setFilterAssignee(e.target.value)}
        >
          <option value="">All Assignees</option>
          {ASSIGNEES.filter(Boolean).map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
          <input type="checkbox" checked={oosOnly} onChange={e => setOosOnly(e.target.checked)}
            className="accent-red-500" />
          OOS Only
        </label>
        <div className="ml-auto flex gap-2">
          <button onClick={() => setView('list')}
            className={`px-3 py-1.5 text-sm rounded ${view === 'list' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400'}`}>
            List
          </button>
          <button onClick={() => setView('map')}
            className={`px-3 py-1.5 text-sm rounded ${view === 'map' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400'}`}>
            Coverage
          </button>
        </div>
      </div>

      {/* ── Coverage Map ─────────────────────────────────────────────────────── */}
      {view === 'map' && (
        <div className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-800 text-sm font-medium text-gray-300">
            State Coverage — Carrier Leads vs Enrolled
          </div>
          <div className="overflow-auto max-h-96">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs border-b border-gray-800">
                  <th className="text-left px-4 py-2">State</th>
                  <th className="text-right px-4 py-2">Leads</th>
                  <th className="text-right px-4 py-2">Enrolled</th>
                  <th className="text-right px-4 py-2">Driver Pool</th>
                  <th className="text-left px-4 py-2">Opportunity</th>
                </tr>
              </thead>
              <tbody>
                {coverage.map(row => (
                  <tr key={row.state} className="border-b border-gray-800 hover:bg-gray-800/50">
                    <td className="px-4 py-2 font-medium text-white">{row.state}</td>
                    <td className="px-4 py-2 text-right text-gray-300">{row.leads.toLocaleString()}</td>
                    <td className="px-4 py-2 text-right">
                      <span className={row.enrolled > 0 ? 'text-green-400' : 'text-gray-600'}>
                        {row.enrolled}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right text-gray-400">{row.driver_pool.toLocaleString()}</td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 bg-gray-700 rounded-full flex-1 max-w-24">
                          <div
                            className="h-full bg-blue-500 rounded-full"
                            style={{ width: `${Math.min((row.enrolled / Math.max(row.total, 1)) * 100, 100)}%` }}
                          />
                        </div>
                        {row.enrolled === 0 && row.leads > 0 && (
                          <span className="text-xs text-amber-400">Untapped</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Carrier List ─────────────────────────────────────────────────────── */}
      {view === 'list' && (
        <div className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden">
          <div className="overflow-auto max-h-[520px]">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-gray-900 border-b border-gray-800">
                <tr className="text-gray-500 text-xs">
                  <th className="text-left px-4 py-2">Carrier</th>
                  <th className="text-left px-4 py-2">State</th>
                  <th className="text-right px-4 py-2">Drivers</th>
                  <th className="text-left px-4 py-2">Contact</th>
                  <th className="text-left px-4 py-2">Rating</th>
                  <th className="text-left px-4 py-2">Status</th>
                  <th className="text-left px-4 py-2">Assigned</th>
                </tr>
              </thead>
              <tbody>
                {carriers.length === 0 && (
                  <tr>
                    <td colSpan={7} className="text-center py-12 text-gray-500">
                      No carriers found — run the FMCSA job to load leads
                    </td>
                  </tr>
                )}
                {carriers.map(c => (
                  <tr
                    key={c.dot_number}
                    onClick={() => openDetail(c)}
                    className="border-b border-gray-800 hover:bg-gray-800/60 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        {c.oos_active && <span className="text-red-400 text-xs" title="Out of Service">⚠</span>}
                        <div>
                          <div className="text-white font-medium leading-tight">
                            {c.dba_name || c.legal_name}
                          </div>
                          <div className="text-gray-600 text-xs">DOT# {c.dot_number}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-2 text-gray-400">{c.state}</td>
                    <td className="px-4 py-2 text-right text-gray-300">{c.driver_total?.toLocaleString()}</td>
                    <td className="px-4 py-2">
                      <div className="text-gray-400 text-xs leading-tight">
                        {c.phone && <div>{c.phone}</div>}
                        {c.email && <div className="truncate max-w-32">{c.email}</div>}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-gray-400">
                      {c.google_rating ? `⭐ ${c.google_rating}` : '—'}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_COLORS[c.status] || STATUS_COLORS.lead}`}>
                        {(c.status || 'lead').replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-500 text-xs">{c.assigned_to || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Detail Pane ───────────────────────────────────────────────────────── */}
      {selected && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-start justify-end">
          <div className="bg-gray-900 border-l border-gray-800 w-full max-w-lg h-full overflow-y-auto">
            <div className="sticky top-0 bg-gray-900 border-b border-gray-800 px-5 py-4 flex items-start justify-between z-10">
              <div>
                <div className="text-white font-semibold text-lg leading-tight">
                  {selected.dba_name || selected.legal_name}
                </div>
                <div className="text-gray-500 text-sm">DOT# {selected.dot_number}</div>
              </div>
              <button onClick={() => setSelected(null)} className="text-gray-500 hover:text-white ml-4 text-xl">✕</button>
            </div>

            <div className="p-5 space-y-5">

              {/* Contact Info */}
              <div className="bg-gray-800 rounded-lg p-4 space-y-2">
                <div className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-3">Contact</div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div><span className="text-gray-500">Phone</span><div className="text-white">{selected.phone || '—'}</div></div>
                  <div><span className="text-gray-500">Email</span><div className="text-white break-all">{selected.email || '—'}</div></div>
                  <div className="col-span-2"><span className="text-gray-500">Address</span>
                    <div className="text-white">{selected.google_verified_address || `${selected.address}, ${selected.city}, ${selected.state} ${selected.zip_code}`}</div>
                  </div>
                  {selected.website && (
                    <div className="col-span-2"><span className="text-gray-500">Website</span>
                      <a href={selected.website} target="_blank" rel="noopener noreferrer"
                        className="text-blue-400 hover:underline break-all block">{selected.website}</a>
                    </div>
                  )}
                </div>
              </div>

              {/* Fleet Stats */}
              <div className="bg-gray-800 rounded-lg p-4">
                <div className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-3">Fleet</div>
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-white">{selected.driver_total}</div>
                    <div className="text-gray-500 text-xs">Drivers</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-white">{selected.nbr_power_unit}</div>
                    <div className="text-gray-500 text-xs">Power Units</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-white">{selected.google_rating || '—'}</div>
                    <div className="text-gray-500 text-xs">Google ⭐</div>
                  </div>
                </div>
                {selected.oos_active && (
                  <div className="mt-3 p-2 bg-red-900/30 border border-red-800 rounded text-xs text-red-300">
                    ⚠ Out of Service — {selected.oos_reason || 'Unknown reason'} ({selected.oos_date})
                  </div>
                )}
                <div className="mt-3 text-xs text-gray-500 flex gap-4">
                  {selected.hm_flag === 'Y' && <span>🔶 HazMat</span>}
                  {selected.pc_flag === 'Y' && <span>🚌 Passenger</span>}
                  {selected.mcs150_date && <span>Filed: {selected.mcs150_date}</span>}
                  {selected.violation_count > 0 && <span className="text-amber-400">{selected.violation_count} violations</span>}
                </div>
              </div>

              {/* Outreach */}
              <div className="bg-gray-800 rounded-lg p-4 space-y-3">
                <div className="text-xs text-gray-500 font-medium uppercase tracking-wide">Outreach</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-gray-500">Status</label>
                    <select
                      className="w-full mt-1 bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-white"
                      value={editStatus}
                      onChange={e => setEditStatus(e.target.value)}
                    >
                      {STATUSES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500">Assigned To</label>
                    <select
                      className="w-full mt-1 bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-white"
                      value={editAssignee}
                      onChange={e => setEditAssignee(e.target.value)}
                    >
                      {ASSIGNEES.map(a => <option key={a} value={a}>{a || 'Unassigned'}</option>)}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="text-xs text-gray-500">Follow Up Date</label>
                  <input type="date"
                    className="w-full mt-1 bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-white"
                    value={editFollowUp}
                    onChange={e => setEditFollowUp(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500">Notes</label>
                  <textarea
                    className="w-full mt-1 bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-white resize-none"
                    rows={3}
                    value={editNotes}
                    onChange={e => setEditNotes(e.target.value)}
                    placeholder="Outreach notes..."
                  />
                </div>
              </div>

              {/* Enrollment */}
              <div className="bg-gray-800 rounded-lg p-4 space-y-3">
                <div className="text-xs text-gray-500 font-medium uppercase tracking-wide">Enrollment Details</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-gray-500">Monthly Rate</label>
                    <input
                      className="w-full mt-1 bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-white"
                      placeholder="e.g. $12/driver/mo"
                      value={editMonthlyRate}
                      onChange={e => setEditMonthlyRate(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500">Drivers Enrolled</label>
                    <input type="number"
                      className="w-full mt-1 bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-white"
                      placeholder="0"
                      value={editDriversEnrolled}
                      onChange={e => setEditDriversEnrolled(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500">Billing Contact</label>
                    <input
                      className="w-full mt-1 bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-white"
                      placeholder="Contact name"
                      value={editBillingContact}
                      onChange={e => setEditBillingContact(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500">Billing Email</label>
                    <input
                      className="w-full mt-1 bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-white"
                      placeholder="billing@company.com"
                      value={editBillingEmail}
                      onChange={e => setEditBillingEmail(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              {/* Email Generator */}
              <div className="bg-gray-800 rounded-lg p-4">
                <button
                  onClick={() => setShowEmail(!showEmail)}
                  className="text-sm text-blue-400 hover:text-blue-300 font-medium"
                >
                  {showEmail ? '▼' : '▶'} Generate Partnership Email
                </button>
                {showEmail && (
                  <div className="mt-3 space-y-2">
                    <pre className="text-xs text-gray-300 whitespace-pre-wrap bg-gray-900 rounded p-3 max-h-48 overflow-y-auto">
                      {generateEmail(selected)}
                    </pre>
                    <div className="flex gap-2">
                      <button
                        onClick={copyEmail}
                        className="px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 text-white rounded"
                      >
                        {emailCopied ? '✓ Copied' : 'Copy'}
                      </button>
                      {selected.email && (
                        <a
                          href={mailtoLink(selected)}
                          className="px-3 py-1.5 text-xs bg-blue-700 hover:bg-blue-600 text-white rounded"
                        >
                          Open in Mail
                        </a>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Save */}
              <button
                onClick={saveChanges}
                disabled={saving}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium rounded-lg text-sm"
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Job History ───────────────────────────────────────────────────────── */}
      {jobRuns.length > 0 && (
        <div className="bg-gray-900 rounded-lg border border-gray-800">
          <div className="px-4 py-3 border-b border-gray-800 text-sm font-medium text-gray-300">
            FMCSA Job History
          </div>
          <div className="divide-y divide-gray-800">
            {jobRuns.map(run => (
              <div key={run.run_id} className="px-4 py-3 flex items-center gap-4 text-sm">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${run.status === 'success' ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-gray-400 text-xs w-32">{run.run_at ? new Date(run.run_at).toLocaleString() : '—'}</span>
                <span className="text-gray-300 flex-1">
                  {run.job === 'fmcsa_carrier_full' ? 'Full Census' : 'OOS Delta'}
                  {run.single_state && ` — ${run.single_state}`}
                </span>
                <span className="text-gray-500 text-xs">
                  {run.carriers_fetched != null && `${run.carriers_fetched.toLocaleString()} fetched`}
                  {run.carriers_written != null && ` · ${run.carriers_written} written`}
                  {run.oos_updated != null && `${run.oos_updated} OOS updated`}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
