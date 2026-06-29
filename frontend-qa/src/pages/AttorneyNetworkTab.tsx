import { useEffect, useState, useCallback } from 'react'
import { attorneyNetworkApi } from '../api/admin'

const STATUSES = ['lead', 'contacted', 'pricing_received', 'onboarded', 'declined']
const STATUS_COLORS: Record<string, string> = {
  lead:             'bg-gray-100 text-gray-700',
  contacted:        'bg-blue-100 text-blue-700',
  pricing_received: 'bg-yellow-100 text-yellow-800',
  onboarded:        'bg-green-100 text-green-800',
  declined:         'bg-red-100 text-red-700',
}
const TEAM = ['eniola', 'quest', 'justin']
const PRACTICE_TYPES = ['traffic', 'cdl', 'dui', 'criminal', 'federal', 'accident']

interface Attorney {
  attorney_id: string
  name: string
  firm_name: string
  state: string
  city: string
  county: string
  phone: string
  email: string
  website: string
  practice_areas: string[]
  cdl_specialist: boolean
  google_rating: number | null
  google_review_count: number | null
  years_in_practice: string
  free_consultation: boolean
  status: string
  assigned_to: string
  contacted_at: string | null
  outreach_notes: string
  pricing_flat_rate: string
  pricing_volume: string
  pricing_per_type: Record<string, string>
  states_covered: string[]
  all_attorneys: string[]
}

interface Pipeline {
  total: number
  cdl_specialists: number
  by_status: Record<string, number>
  by_state: Record<string, number>
}

interface Coverage {
  state: string
  ticket_count: number
  has_onboarded_attorney: boolean
  total_leads: number
  priority: string
}

interface JobRun {
  run_id: string
  run_at: string
  states_scraped: string[]
  attorneys_found: number
  attorneys_imported: number
  status: string
}

export default function AttorneyNetworkTab() {
  const [attorneys, setAttorneys] = useState<Attorney[]>([])
  const [pipeline, setPipeline] = useState<Pipeline | null>(null)
  const [coverage, setCoverage] = useState<Coverage[]>([])
  const [jobRuns, setJobRuns] = useState<JobRun[]>([])
  const [loading, setLoading] = useState(true)
  const [filterState, setFilterState] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [filterAssigned, setFilterAssigned] = useState('')
  const [filterCDL, setFilterCDL] = useState(false)
  const [selected, setSelected] = useState<Attorney | null>(null)
  const [view, setView] = useState<'list' | 'coverage' | 'detail'>('list')
  const [saving, setSaving] = useState(false)
  const [emailModal, setEmailModal] = useState<Attorney | null>(null)

  // Local edits for detail pane
  const [editStatus, setEditStatus] = useState('')
  const [editAssigned, setEditAssigned] = useState('')
  const [editNotes, setEditNotes] = useState('')
  const [editFlatRate, setEditFlatRate] = useState('')
  const [editVolume, setEditVolume] = useState('')
  const [editPerType, setEditPerType] = useState<Record<string, string>>({})
  const [editStates, setEditStates] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [attyRes, pipeRes, covRes] = await Promise.all([
        attorneyNetworkApi.list({
          state: filterState || undefined,
          status: filterStatus || undefined,
          assigned_to: filterAssigned || undefined,
          cdl_specialist: filterCDL || undefined,
          limit: 200,
        }),
        attorneyNetworkApi.pipeline(),
        attorneyNetworkApi.coverage(),
        attorneyNetworkApi.jobHistory(5),
      ])
      setAttorneys(attyRes.attorneys ?? [])
      setPipeline(pipeRes)
      setCoverage(covRes.coverage ?? [])
      setJobRuns(jobRes.runs ?? [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [filterState, filterStatus, filterAssigned, filterCDL])

  useEffect(() => { load() }, [load])

  function openDetail(a: Attorney) {
    setSelected(a)
    setEditStatus(a.status)
    setEditAssigned(a.assigned_to || '')
    setEditNotes(a.outreach_notes || '')
    setEditFlatRate(a.pricing_flat_rate || '')
    setEditVolume(a.pricing_volume || '')
    setEditPerType(a.pricing_per_type || {})
    setEditStates((a.states_covered || []).join(', '))
    setView('detail')
  }

  async function saveDetail() {
    if (!selected) return
    setSaving(true)
    try {
      await Promise.all([
        attorneyNetworkApi.updateOutreach(selected.attorney_id, {
          status: editStatus,
          assigned_to: editAssigned,
          outreach_notes: editNotes,
        }),
        attorneyNetworkApi.updatePricing(selected.attorney_id, {
          pricing_flat_rate: editFlatRate,
          pricing_volume: editVolume,
          pricing_per_type: editPerType,
          states_covered: editStates.split(',').map(s => s.trim()).filter(Boolean),
        }),
      ])
      await load()
      setView('list')
      setSelected(null)
    } finally {
      setSaving(false)
    }
  }

  function generateEmail(a: Attorney): string {
    const firm = a.firm_name || a.name
    const practice = (a.practice_areas || []).slice(0, 3).join(', ')
    return `Subject: Partnership Opportunity — Rig Resolve CDL Legal Benefit Platform

Hi ${a.name || 'there'},

My name is Eniola Dove, co-founder of Rig Resolve — a legal benefit platform for commercial truck drivers (CDL holders). We provide monthly subscription-based attorney representation when drivers receive traffic citations, DUI/DWI charges, or other violations that put their CDL at risk.

I came across ${firm} and your work in ${practice || 'traffic and criminal defense'} — exactly the kind of experienced representation our drivers need.

We're building our attorney network in ${a.state}${a.county ? ` (${a.county} County)` : ''} and would love to discuss a partnership. Here's how it works:

• Drivers in your area who need representation are matched to you through our platform
• You receive cases with full documentation pre-organized by our AI intake system
• We handle driver communication and billing — you focus on the case

We work with attorneys on flat-rate, volume, and per-case-type pricing structures. I'd love to schedule a 15-minute call to see if there's a fit.

Are you available this week?

Best,
Eniola Dove
Co-Founder, Rig Resolve
quest@puklabs.com
www.rigresolve.com`
  }

  // ── Pipeline summary ──
  const renderPipeline = () => (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
      {STATUSES.map(s => (
        <button
          key={s}
          onClick={() => { setFilterStatus(filterStatus === s ? '' : s); setView('list') }}
          className={`rounded-xl p-3 text-left border-2 transition ${
            filterStatus === s ? 'border-blue-500' : 'border-transparent'
          } ${STATUS_COLORS[s]} cursor-pointer`}
        >
          <div className="text-2xl font-bold">{pipeline?.by_status?.[s] ?? 0}</div>
          <div className="text-xs capitalize mt-1">{s.replace('_', ' ')}</div>
        </button>
      ))}
    </div>
  )

  // ── Coverage view ──
  const renderCoverage = () => (
    <div>
      <h3 className="font-semibold text-gray-700 mb-3">State Coverage — Tickets vs Onboarded Attorneys</h3>
      <div className="space-y-2">
        {coverage.map(c => (
          <div key={c.state} className={`flex items-center gap-3 p-3 rounded-lg border ${
            c.priority === 'HIGH' ? 'border-red-300 bg-red-50' : 'border-gray-200 bg-white'
          }`}>
            <div className="w-10 font-bold text-gray-800">{c.state}</div>
            <div className="flex-1">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-gray-500">{c.ticket_count} tickets</span>
                <span>·</span>
                <span className="text-gray-500">{c.total_leads} leads</span>
                {c.has_onboarded_attorney
                  ? <span className="text-green-600 font-medium">✓ Attorney onboarded</span>
                  : <span className="text-red-600 font-medium">⚠ No attorney onboarded</span>}
              </div>
            </div>
            {c.priority === 'HIGH' && (
              <span className="text-xs bg-red-500 text-white px-2 py-0.5 rounded-full">PRIORITY</span>
            )}
            <button
              onClick={() => { setFilterState(c.state); setView('list') }}
              className="text-xs text-blue-600 underline"
            >View leads</button>
          </div>
        ))}
      </div>
    </div>
  )

  // ── Attorney list ──
  const renderList = () => (
    <div className="space-y-2">
      {attorneys.length === 0 && !loading && (
        <div className="text-center text-gray-400 py-16">No attorneys match these filters.</div>
      )}
      {attorneys.map(a => (
        <div
          key={a.attorney_id}
          onClick={() => openDetail(a)}
          className="flex items-start gap-3 p-3 bg-white rounded-lg border border-gray-200 hover:border-blue-300 cursor-pointer transition"
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-gray-900 truncate">{a.firm_name || a.name}</span>
              {a.cdl_specialist && (
                <span className="text-xs bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded font-medium">CDL</span>
              )}
              {a.free_consultation && (
                <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">Free Consult</span>
              )}
            </div>
            <div className="text-sm text-gray-500 mt-0.5">
              {a.name !== a.firm_name && a.name && <span>{a.name} · </span>}
              {a.city}{a.city && a.state ? ', ' : ''}{a.state}
              {a.years_in_practice ? ` · ${a.years_in_practice} yrs` : ''}
              {a.google_rating ? ` · ⭐${a.google_rating} (${a.google_review_count})` : ''}
            </div>
            <div className="text-xs text-gray-400 mt-0.5 truncate">
              {(a.practice_areas || []).slice(0, 4).join(' · ')}
            </div>
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[a.status] ?? STATUS_COLORS.lead}`}>
              {a.status?.replace('_', ' ')}
            </span>
            {a.assigned_to && (
              <span className="text-xs text-gray-400 capitalize">{a.assigned_to}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  )

  // ── Detail pane ──
  const renderDetail = () => {
    if (!selected) return null
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-900">{selected.firm_name || selected.name}</h2>
            {selected.all_attorneys?.length > 0 && (
              <p className="text-sm text-gray-500 mt-0.5">{selected.all_attorneys.join(' · ')}</p>
            )}
            <p className="text-sm text-gray-400">{selected.city}, {selected.state} {selected.county ? `· ${selected.county} County` : ''}</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setEmailModal(selected)}
              className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700"
            >✉ Email Template</button>
            <button
              onClick={() => { setView('list'); setSelected(null) }}
              className="text-sm bg-gray-100 text-gray-700 px-3 py-1.5 rounded-lg hover:bg-gray-200"
            >← Back</button>
          </div>
        </div>

        {/* Contact info */}
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div><span className="text-gray-400">Phone</span><br/><a href={`tel:${selected.phone}`} className="text-blue-600">{selected.phone || '—'}</a></div>
          <div><span className="text-gray-400">Email</span><br/><a href={`mailto:${selected.email}`} className="text-blue-600">{selected.email || '—'}</a></div>
          <div><span className="text-gray-400">Website</span><br/>{selected.website ? <a href={selected.website} target="_blank" className="text-blue-600 truncate block">{selected.website.replace(/https?:\/\//, '')}</a> : '—'}</div>
          <div><span className="text-gray-400">Google Rating</span><br/>⭐ {selected.google_rating ?? '—'} ({selected.google_review_count ?? 0} reviews)</div>
          <div><span className="text-gray-400">Years Practice</span><br/>{selected.years_in_practice || '—'}</div>
          <div><span className="text-gray-400">CDL Specialist</span><br/>{selected.cdl_specialist ? '✅ Yes' : 'No'}</div>
        </div>

        <div className="text-sm text-gray-500">
          <span className="font-medium text-gray-700">Practice Areas:</span>{' '}
          {(selected.practice_areas || []).join(', ') || '—'}
        </div>

        <hr/>

        {/* Outreach */}
        <div>
          <h3 className="font-semibold text-gray-700 mb-3">Outreach</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Status</label>
              <select
                value={editStatus}
                onChange={e => setEditStatus(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                {STATUSES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Assigned To</label>
              <select
                value={editAssigned}
                onChange={e => setEditAssigned(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm capitalize"
              >
                <option value="">— Unassigned —</option>
                {TEAM.map(t => <option key={t} value={t} className="capitalize">{t}</option>)}
              </select>
            </div>
          </div>
          <div className="mt-3">
            <label className="text-xs text-gray-500 mb-1 block">Notes</label>
            <textarea
              value={editNotes}
              onChange={e => setEditNotes(e.target.value)}
              rows={3}
              placeholder="Call notes, responses, follow-up reminders..."
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none"
            />
          </div>
        </div>

        <hr/>

        {/* Pricing */}
        <div>
          <h3 className="font-semibold text-gray-700 mb-3">Pricing Collected</h3>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Flat Rate (per case)</label>
              <input
                value={editFlatRate}
                onChange={e => setEditFlatRate(e.target.value)}
                placeholder="e.g. $500 flat"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Volume Rate</label>
              <input
                value={editVolume}
                onChange={e => setEditVolume(e.target.value)}
                placeholder="e.g. $400/case if 5+/mo"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {PRACTICE_TYPES.map(pt => (
              <div key={pt}>
                <label className="text-xs text-gray-500 mb-1 block capitalize">{pt}</label>
                <input
                  value={editPerType[pt] || ''}
                  onChange={e => setEditPerType(p => ({ ...p, [pt]: e.target.value }))}
                  placeholder="$—"
                  className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm"
                />
              </div>
            ))}
          </div>
          <div className="mt-3">
            <label className="text-xs text-gray-500 mb-1 block">States Covered (comma-sep)</label>
            <input
              value={editStates}
              onChange={e => setEditStates(e.target.value)}
              placeholder="MO, KS, IL"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            />
          </div>
        </div>

        <button
          onClick={saveDetail}
          disabled={saving}
          className="w-full bg-blue-600 text-white py-2.5 rounded-xl font-semibold hover:bg-blue-700 disabled:opacity-50 transition"
        >
          {saving ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    )
  }

  // ── Email modal ──
  const renderEmailModal = () => {
    if (!emailModal) return null
    const emailText = generateEmail(emailModal)
    return (
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold">Outreach Email — {emailModal.firm_name || emailModal.name}</h2>
            <button onClick={() => setEmailModal(null)} className="text-gray-400 hover:text-gray-700 text-xl">✕</button>
          </div>
          <pre className="text-sm bg-gray-50 border border-gray-200 rounded-xl p-4 whitespace-pre-wrap font-sans leading-relaxed">
            {emailText}
          </pre>
          <div className="flex gap-3 mt-4">
            <button
              onClick={() => navigator.clipboard.writeText(emailText)}
              className="flex-1 bg-blue-600 text-white py-2.5 rounded-xl font-semibold hover:bg-blue-700"
            >Copy to Clipboard</button>
            {emailModal.email && (
              <a
                href={`mailto:${emailModal.email}?subject=Partnership Opportunity — Rig Resolve CDL Legal Benefit Platform&body=${encodeURIComponent(emailText.split('\n').slice(1).join('\n').trim())}`}
                className="flex-1 text-center bg-green-600 text-white py-2.5 rounded-xl font-semibold hover:bg-green-700"
              >Open in Mail</a>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto">
      {/* Title */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Attorney Network</h1>
          <p className="text-sm text-gray-500">
            {pipeline?.total ?? 0} total leads · {pipeline?.cdl_specialists ?? 0} CDL specialists · {pipeline?.by_status?.onboarded ?? 0} onboarded
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setView('list')} className={`text-sm px-3 py-1.5 rounded-lg ${view === 'list' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'}`}>Leads</button>
          <button onClick={() => setView('coverage')} className={`text-sm px-3 py-1.5 rounded-lg ${view === 'coverage' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'}`}>Coverage Map</button>
        </div>
      </div>

      {/* Pipeline chips */}
      {view !== 'detail' && renderPipeline()}

      {/* Filters */}
      {view === 'list' && (
        <div className="flex flex-wrap gap-2 mb-4">
          <input
            value={filterState}
            onChange={e => setFilterState(e.target.value.toUpperCase())}
            placeholder="State (e.g. MO)"
            maxLength={2}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-28"
          />
          <select
            value={filterAssigned}
            onChange={e => setFilterAssigned(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm capitalize"
          >
            <option value="">All assignees</option>
            {TEAM.map(t => <option key={t} value={t} className="capitalize">{t}</option>)}
          </select>
          <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer">
            <input type="checkbox" checked={filterCDL} onChange={e => setFilterCDL(e.target.checked)} />
            CDL only
          </label>
          {(filterState || filterStatus || filterAssigned || filterCDL) && (
            <button
              onClick={() => { setFilterState(''); setFilterStatus(''); setFilterAssigned(''); setFilterCDL(false) }}
              className="text-sm text-red-500 underline"
            >Clear filters</button>
          )}
          <span className="text-sm text-gray-400 ml-auto self-center">{attorneys.length} attorneys</span>
        </div>
      )}

      {loading && <div className="text-center text-gray-400 py-16">Loading…</div>}
      {!loading && view === 'list' && renderList()}
      {!loading && view === 'coverage' && renderCoverage()}
      {view === 'detail' && renderDetail()}
      {renderEmailModal()}

      {/* Discovery Job History */}
      {view !== 'detail' && jobRuns.length > 0 && (
        <div className="mt-8 border-t border-gray-200 pt-6">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Auto-Discovery Job History</h3>
          <div className="space-y-2">
            {jobRuns.map(r => (
              <div key={r.run_id} className="flex items-center gap-3 text-sm bg-white border border-gray-200 rounded-lg px-4 py-2.5">
                <span className={`w-2 h-2 rounded-full shrink-0 ${r.status === 'success' ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-gray-500 w-36 shrink-0">{r.run_at ? new Date(r.run_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}</span>
                <span className="text-gray-700 font-medium">{r.attorneys_imported} imported</span>
                <span className="text-gray-400">·</span>
                <span className="text-gray-500">{r.attorneys_found} found</span>
                <span className="text-gray-400">·</span>
                <span className="text-gray-400">{(r.states_scraped || []).join(', ')}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
