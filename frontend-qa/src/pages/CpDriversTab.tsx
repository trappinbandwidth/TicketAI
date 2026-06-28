import { useCallback, useEffect, useState } from 'react'
import { controlApi } from '../api/admin'
import { B, Spinner, Err, Badge, Modal, Drawer, Field, FieldGrid, useToast } from '../shared/CpComponents'

function AddDriverModal({ onClose, onSaved, show }: { onClose: () => void; onSaved: () => void; show: (m: string, ok?: boolean) => void }) {
  const [form, setForm] = useState({
    full_name: '', email: '', phone: '', cdl_number: '', cdl_class: 'A',
    dob: '', state: '', membership_tier: 'silver', notes: '',
  })
  const [saving, setSaving] = useState(false)
  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.full_name) return
    setSaving(true)
    try {
      await controlApi.createDriver({ ...form, subscription_status: 'active' })
      show('Driver added')
      onSaved()
    } catch (err: any) { show(err.message, false) }
    finally { setSaving(false) }
  }

  return (
    <Modal title="Add Driver" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <label className="block text-xs font-medium text-gray-500 mb-1">Full Name *</label>
            <input required value={form.full_name} onChange={e => set('full_name', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Email</label>
            <input type="email" value={form.email} onChange={e => set('email', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Phone</label>
            <input value={form.phone} onChange={e => set('phone', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">CDL Number</label>
            <input value={form.cdl_number} onChange={e => set('cdl_number', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">CDL Class</label>
            <select value={form.cdl_class} onChange={e => set('cdl_class', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
              {['A', 'B', 'C'].map(c => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Date of Birth</label>
            <input type="date" value={form.dob} onChange={e => set('dob', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">State</label>
            <input value={form.state} onChange={e => set('state', e.target.value)} maxLength={2}
              placeholder="TX" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="col-span-2">
            <label className="block text-xs font-medium text-gray-500 mb-1">Membership Tier</label>
            <div className="flex gap-2">
              {[
                { t: 'silver', label: 'Silver (Free)', sub: 'Basic coverage' },
                { t: 'gold', label: 'Gold — $44.99/mo', sub: 'Nationwide + $0 deductible' },
                { t: 'platinum', label: 'Platinum — $68.99/mo', sub: 'Full trial coverage' },
              ].map(({ t, label, sub }) => (
                <button key={t} type="button" onClick={() => set('membership_tier', t)}
                  className="flex-1 p-2 rounded-lg border-2 text-left transition-all"
                  style={form.membership_tier === t
                    ? { borderColor: B.teal, background: B.tealTint }
                    : { borderColor: '#E5E7EB' }}>
                  <div className="text-xs font-bold text-gray-800">{label}</div>
                  <div className="text-xs text-gray-400">{sub}</div>
                </button>
              ))}
            </div>
          </div>
          <div className="col-span-2">
            <label className="block text-xs font-medium text-gray-500 mb-1">Notes</label>
            <textarea value={form.notes} onChange={e => set('notes', e.target.value)}
              rows={2} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none" />
          </div>
        </div>
        <button type="submit" disabled={saving}
          className="w-full py-2.5 rounded-lg text-sm font-bold text-white transition-colors"
          style={{ background: saving ? '#94A3B8' : B.teal }}>
          {saving ? 'Adding…' : 'Add Driver'}
        </button>
      </form>
    </Modal>
  )
}

export default function CpDriversTab() {
  const [drivers, setDrivers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<any>(null)
  const [driverDetail, setDriverDetail] = useState<any>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const { show, el: toastEl } = useToast()

  const load = useCallback(() => {
    setLoading(true)
    controlApi.listDrivers().then(r => setDrivers(r.drivers ?? [])).catch(e => setErr(e.message)).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const openDetail = useCallback(async (d: any) => {
    setSelected(d)
    setLoadingDetail(true)
    try {
      const detail = await controlApi.getDriver(d.driver_id)
      setDriverDetail(detail)
    } catch { setDriverDetail(d) }
    setLoadingDetail(false)
  }, [])

  const handleUpdate = useCallback(async (id: string, updates: Record<string, unknown>) => {
    try {
      await controlApi.updateDriver(id, updates)
      show('Updated successfully')
      load()
      if (selected?.driver_id === id) openDetail({ ...selected, ...updates })
    } catch (e: any) { show(e.message, false) }
  }, [load, show, selected, openDetail])

  const filtered = drivers.filter(d => {
    const q = search.toLowerCase()
    return !q || (d.full_name ?? '').toLowerCase().includes(q) ||
      (d.email ?? '').toLowerCase().includes(q) || (d.cdl_number ?? '').toLowerCase().includes(q)
  })

  return (
    <div>
      {toastEl}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search name, email, CDL…"
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-64 focus:outline-none focus:ring-2"
            style={{ '--tw-ring-color': B.teal } as any}
          />
          <span className="text-sm text-gray-400">{filtered.length} drivers</span>
        </div>
        <button onClick={() => setShowAdd(true)}
          className="px-4 py-2 rounded-lg text-sm font-semibold text-white transition-colors"
          style={{ background: B.teal }}>
          + Add Driver
        </button>
      </div>

      {loading && <Spinner />}
      {err && <Err msg={err} />}
      {!loading && !err && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: B.offWhite }}>
                {['Name', 'CDL #', 'State', 'Tier', 'Status', 'Phone', ''].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No drivers found</td></tr>
              )}
              {filtered.map(d => (
                <tr key={d.driver_id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-800">{d.full_name || '—'}</td>
                  <td className="px-4 py-3 text-gray-500 font-mono text-xs">{d.cdl_number || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{d.state || '—'}</td>
                  <td className="px-4 py-3"><Badge status={d.membership_tier || 'silver'} /></td>
                  <td className="px-4 py-3"><Badge status={d.subscription_status || 'active'} /></td>
                  <td className="px-4 py-3 text-gray-500">{d.phone || '—'}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button onClick={() => openDetail(d)}
                        className="text-xs px-2.5 py-1 rounded-lg bg-blue-50 text-blue-600 font-medium hover:bg-blue-100">
                        View
                      </button>
                      {d.subscription_status === 'active' && (
                        <button onClick={() => handleUpdate(d.driver_id, { subscription_status: 'cancelled' })}
                          className="text-xs px-2.5 py-1 rounded-lg bg-red-50 text-red-500 font-medium hover:bg-red-100">
                          Cancel
                        </button>
                      )}
                      {d.subscription_status !== 'archived' && (
                        <button onClick={() => handleUpdate(d.driver_id, { subscription_status: 'archived' })}
                          className="text-xs px-2.5 py-1 rounded-lg bg-gray-100 text-gray-400 font-medium hover:bg-gray-200">
                          Archive
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <Drawer title={`Driver — ${selected.full_name || selected.driver_id}`} onClose={() => { setSelected(null); setDriverDetail(null) }}>
          {loadingDetail ? <Spinner /> : driverDetail ? (
            <div className="space-y-6">
              <section>
                <h3 className="text-sm font-bold text-gray-700 mb-3">Profile</h3>
                <FieldGrid>
                  <Field label="Full Name" value={driverDetail.full_name} />
                  <Field label="Email" value={driverDetail.email} />
                  <Field label="Phone" value={driverDetail.phone} />
                  <Field label="CDL Number" value={driverDetail.cdl_number} />
                  <Field label="CDL Class" value={driverDetail.cdl_class} />
                  <Field label="Date of Birth" value={driverDetail.dob} />
                  <Field label="State" value={driverDetail.state} />
                  <Field label="Carrier ID" value={driverDetail.carrier_id} />
                  <Field label="Tier" value={driverDetail.membership_tier} />
                  <Field label="Sub Status" value={driverDetail.subscription_status} />
                  <Field label="Joined" value={driverDetail.created_at ? new Date(driverDetail.created_at).toLocaleDateString() : undefined} />
                </FieldGrid>
                {driverDetail.notes && (
                  <div className="mt-3 p-3 bg-gray-50 rounded-lg text-sm text-gray-600">{driverDetail.notes}</div>
                )}
              </section>

              <section>
                <h3 className="text-sm font-bold text-gray-700 mb-3">Change Membership Tier</h3>
                <div className="flex gap-2">
                  {['silver', 'gold', 'platinum'].map(t => (
                    <button key={t} onClick={() => handleUpdate(driverDetail.driver_id, { membership_tier: t })}
                      className="flex-1 py-2 rounded-lg text-xs font-bold capitalize border-2 transition-all"
                      style={driverDetail.membership_tier === t
                        ? { borderColor: B.teal, color: B.teal, background: B.tealTint }
                        : { borderColor: '#E5E7EB', color: '#6B7280' }}>
                      {t}
                    </button>
                  ))}
                </div>
              </section>

              <section>
                <h3 className="text-sm font-bold text-gray-700 mb-3">
                  Tickets ({(driverDetail.all_tickets ?? []).length})
                </h3>
                {(driverDetail.all_tickets ?? []).length === 0
                  ? <p className="text-sm text-gray-400">No tickets on file</p>
                  : (
                    <div className="space-y-2 max-h-80 overflow-y-auto">
                      {(driverDetail.all_tickets ?? []).map((t: any) => (
                        <div key={t.ticket_id} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="text-sm font-medium text-gray-800">
                                {t.violation_category || 'Unknown violation'}
                              </div>
                              <div className="text-xs text-gray-400 mt-0.5">
                                {t.ticket_state} {t.ticket_county && `· ${t.ticket_county}`}
                                {t.court_date && ` · Court: ${t.court_date}`}
                              </div>
                            </div>
                            <Badge status={t.attorney_status || 'New'} />
                          </div>
                          {t.citation_number && (
                            <div className="text-xs text-gray-400 mt-1 font-mono">#{t.citation_number}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
              </section>
            </div>
          ) : null}
        </Drawer>
      )}

      {showAdd && <AddDriverModal onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); load() }} show={show} />}
    </div>
  )
}
