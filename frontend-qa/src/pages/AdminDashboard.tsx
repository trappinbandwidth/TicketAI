import { useEffect, useState, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import { adminApi } from '../api/admin'

// ── Colour palette ────────────────────────────────────────────────────────
const PASS_COLORS = { green: '#22c55e', yellow: '#eab308', red: '#ef4444', unknown: '#94a3b8' }
const HEALTH_COLOR = (h: number) => h >= 0.9 ? '#22c55e' : h >= 0.75 ? '#eab308' : '#ef4444'
const CONF_COLOR   = (c: number) => c >= 0.85 ? '#22c55e' : c >= 0.60 ? '#eab308' : '#ef4444'
const DOC_COLORS   = ['#6366f1','#3b82f6','#06b6d4','#10b981','#f59e0b','#f97316','#ec4899']

// ── Small reusable components ─────────────────────────────────────────────
function KpiCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-col gap-1">
      <span className="text-xs text-gray-400 font-medium uppercase tracking-wide">{label}</span>
      <span className="text-2xl font-bold" style={{ color: color ?? '#1e293b' }}>{value}</span>
      {sub && <span className="text-xs text-gray-400">{sub}</span>}
    </div>
  )
}

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-4">
      <h2 className="text-lg font-bold text-gray-800">{title}</h2>
      {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
    </div>
  )
}

function Spinner() {
  return <div className="flex items-center justify-center py-16 text-gray-400">Loading...</div>
}

// ── Tab navigation ────────────────────────────────────────────────────────
const TABS = ['Overview', 'Fields', 'Agents', 'Scan Feed', 'Attorneys'] as const
type Tab = typeof TABS[number]

// ── Main component ────────────────────────────────────────────────────────
export default function AdminDashboard() {
  const [tab, setTab] = useState<Tab>('Overview')
  const [days, setDays] = useState(30)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-800">Rig Resolve — AI Performance Dashboard</h1>
          <p className="text-xs text-gray-400 mt-0.5">Real-time extraction analytics & agent health</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Last</span>
          {[7, 30, 90].map(d => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${days === d ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >{d}d</button>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200 px-6 flex gap-1">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${tab === t ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-800'}`}
          >{t}</button>
        ))}
      </div>

      {/* Content */}
      <div className="p-6">
        {tab === 'Overview'  && <OverviewTab  days={days} />}
        {tab === 'Fields'    && <FieldsTab    days={days} />}
        {tab === 'Agents'    && <AgentsTab    days={days} />}
        {tab === 'Scan Feed' && <ScanFeedTab  />}
        {tab === 'Attorneys' && <AttorneysTab />}
      </div>
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
      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <KpiCard label="Total Scans" value={data.total} sub={`Last ${days} days`} />
        <KpiCard label="Green Rate" value={pct(data.green_rate)} color={PASS_COLORS.green} />
        <KpiCard label="Yellow Rate" value={pct(data.yellow_rate)} color={PASS_COLORS.yellow} />
        <KpiCard label="Red Rate" value={pct(data.red_rate)} color={PASS_COLORS.red} />
        <KpiCard label="Attorney Match" value={pct(data.attorney_match_rate)} sub="of ticket scans" />
        <KpiCard label="Price Estimated" value={pct(data.price_estimate_rate)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Daily volume */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-5">
          <SectionHeader title="Daily Scan Volume" subtitle="Stacked by pass status" />
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.daily_volume || []} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={d => d.slice(5)} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Bar dataKey="green"   stackId="a" fill={PASS_COLORS.green}  />
              <Bar dataKey="yellow"  stackId="a" fill={PASS_COLORS.yellow} />
              <Bar dataKey="red"     stackId="a" fill={PASS_COLORS.red}    />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Doc type donut */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <SectionHeader title="Doc Types" />
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={docTypeData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`} labelLine={false}>
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
      {/* Controls */}
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
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${sortBy === s ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
          >{s.replace('_', ' ')}</button>
        ))}
        {data && <span className="text-xs text-gray-400 ml-auto">{data.sample_size} approved scans</span>}
      </div>

      {!data ? <Spinner /> : (
        <>
          {/* Field table */}
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
                  <tr
                    key={f.field}
                    onClick={() => openDrill(f.field)}
                    className="hover:bg-blue-50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-gray-700 font-medium">{f.field}</td>
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
                        <span className="text-blue-500">+{(f.pass2_improvement_rate * 100).toFixed(0)}%</span>
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

          {/* Field drill-down panel */}
          {drillField && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-bold text-gray-800 font-mono">{drillField}</h3>
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
                            style={{ background: (PASS_COLORS as any)[c.pass_status] + '20', color: (PASS_COLORS as any)[c.pass_status] }}>
                            {c.pass_status}
                          </span>
                        </td>
                        <td className="px-3 py-2 font-medium text-gray-800 max-w-[140px] truncate">{c.ai_value || <span className="text-gray-300 italic">empty</span>}</td>
                        <td className="px-3 py-2 text-blue-600 max-w-[140px] truncate">{c.final_value !== c.ai_value ? c.final_value : '—'}</td>
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
      {/* Health ranking strip */}
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

      {/* Per-agent detail cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {agents.map((ag: any) => (
          <div key={ag.agent} className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="font-bold text-gray-800">{ag.name}</span>
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
                    <p className="text-xs text-red-500 font-semibold mb-1.5">⚠ Most often empty after Pass 1 (prompt gaps)</p>
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
                    <p className="text-xs text-yellow-600 font-semibold mb-1.5">⚡ Low confidence (Pass 1)</p>
                    <div className="space-y-1">
                      {ag.top_low_conf_fields.slice(0, 6).map(([field, count]: [string, number]) => (
                        <div key={field} className="flex justify-between text-xs">
                          <span className="font-mono text-gray-600">{field}</span>
                          <span className="text-yellow-600 font-medium">{count}x</span>
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
                    <p className="text-xs text-red-500 font-semibold mb-1.5">🚨 Critical field failures (escalates to RED)</p>
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
                    <p className="text-xs text-yellow-600 font-semibold mb-1.5">⚡ Most flagged low-confidence fields</p>
                    <div className="space-y-1">
                      {ag.top_low_conf_fields.slice(0, 5).map(([field, count]: [string, number]) => (
                        <div key={field} className="flex justify-between text-xs">
                          <span className="font-mono text-gray-600">{field}</span>
                          <span className="text-yellow-600 font-medium">{count}x</span>
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
                  <span className="font-medium text-blue-600">{ag.avg_improvements_per_scan}</span>
                </div>
                {ag.top_dual_conflict_fields?.length > 0 && (
                  <div>
                    <p className="text-xs text-amber-600 font-semibold mb-1.5">⚠ Fields with dual conflicts (prompt ambiguity)</p>
                    <div className="space-y-1">
                      {ag.top_dual_conflict_fields.map(([field, count]: [string, number]) => (
                        <div key={field} className="flex justify-between text-xs">
                          <span className="font-mono text-gray-600">{field}</span>
                          <span className="text-amber-600 font-medium">{count}x</span>
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
              <td className="px-4 py-3 text-xs text-gray-400">{s.created_at?.slice(11, 16)}</td>
              <td className="px-4 py-3 text-xs text-gray-700 font-medium max-w-[160px] truncate">{s.filename}</td>
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
                  ? <span className="text-green-600">✓ {s.attorney_match_type}</span>
                  : <span className="text-gray-300">—</span>}
              </td>
              <td className="px-4 py-3 text-xs">
                {s.has_price_estimate
                  ? <span className="text-blue-500">✓</span>
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
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="text-sm font-semibold text-amber-700 mb-2">⚠ {noAtty.length} recent scans with no attorney on file</p>
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
                <td className="px-4 py-3 font-medium text-gray-800">{s.state}</td>
                <td className="px-4 py-3 text-gray-600">{s.total_tickets}</td>
                <td className="px-4 py-3 text-green-600 font-medium">{s.matched}</td>
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
