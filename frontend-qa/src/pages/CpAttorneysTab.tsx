import { useCallback, useEffect, useState } from 'react'
import { controlApi } from '../api/admin'
import { B, Spinner, Err, Badge, Modal, useToast } from '../shared/CpComponents'

function AddAttorneyModal({ onClose, onSaved, show }: { onClose: () => void; onSaved: () => void; show: (m: string, ok?: boolean) => void }) {
  const [form, setForm] = useState({
    full_name: '', firm_name: '', email: '', phone: '',
    states_licensed: '', max_active_cases: '10',
    preferred_contact_method: 'phone', fee_structure: '', notes: '',
  })
  const [saving, setSaving] = useState(false)
  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.full_name || !form.email) return
    setSaving(true)
    try {
      await controlApi.createAttorney({
        ...form,
        states_licensed: form.states_licensed.split(',').map(s => s.trim()).filter(Boolean),
        max_active_cases: parseInt(form.max_active_cases) || 10,
        status: 'pending',
      })
      show('Attorney added — pending approval')
      onSaved()
    } catch (err: any) { show(err.message, false) }
    finally { setSaving(false) }
  }

  return (
    <Modal title="Add Attorney" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Full Name *</label>
            <input required value={form.full_name} onChange={e => set('full_name', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Firm Name</label>
            <input value={form.firm_name} onChange={e => set('firm_name', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Email *</label>
            <input required type="email" value={form.email} onChange={e => set('email', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Phone</label>
            <input value={form.phone} onChange={e => set('phone', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">States Licensed (comma-sep)</label>
            <input value={form.states_licensed} onChange={e => set('states_licensed', e.target.value)}
              placeholder="TX, LA, OK" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Max Active Cases</label>
            <input type="number" value={form.max_active_cases} onChange={e => set('max_active_cases', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Preferred Contact</label>
            <select value={form.preferred_contact_method} onChange={e => set('preferred_contact_method', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
              <option value="phone">Phone</option>
              <option value="email">Email</option>
              <option value="text">Text</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Fee Structure</label>
            <input value={form.fee_structure} onChange={e => set('fee_structure', e.target.value)}
              placeholder="e.g. $750 flat per ticket" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="col-span-2">
            <label className="block text-xs font-medium text-gray-500 mb-1">Notes</label>
            <textarea value={form.notes} onChange={e => set('notes', e.target.value)}
              rows={2} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none" />
          </div>
        </div>
        <button type="submit" disabled={saving}
          className="w-full py-2.5 rounded-lg text-sm font-bold text-white"
          style={{ background: saving ? '#94A3B8' : B.teal }}>
          {saving ? 'Saving…' : 'Add Attorney (Pending Approval)'}
        </button>
      </form>
    </Modal>
  )
}

export default function CpAttorneysTab() {
  const [attorneys, setAttorneys] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [filter, setFilter] = useState<string>('all')
  const [showAdd, setShowAdd] = useState(false)
  const { show, el: toastEl } = useToast()

  const load = useCallback(() => {
    setLoading(true)
    controlApi.listAttorneys().then(r => setAttorneys(r.attorneys ?? [])).catch(e => setErr(e.message)).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const handleStatus = useCallback(async (id: string, status: string) => {
    try { await controlApi.updateAttorney(id, { status }); show(`Attorney marked ${status}`); load() }
    catch (e: any) { show(e.message, false) }
  }, [load, show])

  const handleRemove = useCallback(async (id: string) => {
    if (!confirm('Remove this attorney from the network?')) return
    try { await controlApi.removeAttorney(id); show('Attorney removed'); load() }
    catch (e: any) { show(e.message, false) }
  }, [load, show])

  const filtered = attorneys.filter(a => filter === 'all' || a.status === filter)
  const pendingCount = attorneys.filter(a => a.status === 'pending').length

  return (
    <div>
      {toastEl}
      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {(['all', 'pending', 'active', 'inactive'] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className="px-3 py-1.5 rounded-md text-xs font-medium capitalize transition-all"
              style={filter === f ? { background: B.teal, color: '#fff' } : { color: '#6B7280' }}>
              {f}
              {f === 'pending' && pendingCount > 0 && (
                <span className="ml-1 bg-red-500 text-white rounded-full px-1.5 py-0.5 text-[10px]">{pendingCount}</span>
              )}
            </button>
          ))}
        </div>
        <button onClick={() => setShowAdd(true)}
          className="px-4 py-2 rounded-lg text-sm font-semibold text-white"
          style={{ background: B.teal }}>
          + Add Attorney
        </button>
      </div>

      {loading && <Spinner />}
      {err && <Err msg={err} />}
      {!loading && !err && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: B.offWhite }}>
                {['Name / Firm', 'States', 'Cases', 'Win Rate', 'Contact', 'Status', ''].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No attorneys</td></tr>
              )}
              {filtered.map(a => (
                <tr key={a.attorney_id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-800">{a.full_name}</div>
                    <div className="text-xs text-gray-400">{a.firm_name}</div>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{(a.states_licensed ?? []).join(', ') || '—'}</td>
                  <td className="px-4 py-3 text-gray-700">{a.cases_active ?? 0} / {a.max_active_cases ?? '?'}</td>
                  <td className="px-4 py-3 text-gray-700">{a.win_rate != null ? `${Math.round(a.win_rate * 100)}%` : '—'}</td>
                  <td className="px-4 py-3">
                    <div className="text-xs text-gray-500">{a.email}</div>
                    <div className="text-xs text-gray-400">{a.phone}</div>
                  </td>
                  <td className="px-4 py-3"><Badge status={a.status || 'pending'} /></td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1.5 flex-wrap">
                      {a.status === 'pending' && (
                        <>
                          <button onClick={() => handleStatus(a.attorney_id, 'active')}
                            className="text-xs px-2.5 py-1 rounded-lg bg-green-50 text-green-600 font-medium hover:bg-green-100">Approve</button>
                          <button onClick={() => handleStatus(a.attorney_id, 'inactive')}
                            className="text-xs px-2.5 py-1 rounded-lg bg-red-50 text-red-500 font-medium hover:bg-red-100">Deny</button>
                        </>
                      )}
                      {a.status === 'active' && (
                        <button onClick={() => handleStatus(a.attorney_id, 'inactive')}
                          className="text-xs px-2.5 py-1 rounded-lg bg-gray-100 text-gray-500 font-medium hover:bg-gray-200">Deactivate</button>
                      )}
                      {a.status === 'inactive' && (
                        <button onClick={() => handleStatus(a.attorney_id, 'active')}
                          className="text-xs px-2.5 py-1 rounded-lg bg-green-50 text-green-600 font-medium hover:bg-green-100">Reactivate</button>
                      )}
                      {a.status !== 'removed' && (
                        <button onClick={() => handleRemove(a.attorney_id)}
                          className="text-xs px-2.5 py-1 rounded-lg bg-red-50 text-red-400 font-medium hover:bg-red-100">Remove</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showAdd && <AddAttorneyModal onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); load() }} show={show} />}
    </div>
  )
}
