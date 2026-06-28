import { useCallback, useEffect, useState } from 'react'
import { controlApi } from '../api/admin'
import { B, Spinner, Err, Badge, Modal, useToast } from '../shared/CpComponents'

function AddCarrierModal({ onClose, onSaved, show }: { onClose: () => void; onSaved: () => void; show: (m: string, ok?: boolean) => void }) {
  const [form, setForm] = useState({
    company_name: '', dot_number: '', mc_number: '', contact_name: '',
    contact_email: '', contact_phone: '', state: '', driver_count: '0', notes: '',
  })
  const [saving, setSaving] = useState(false)
  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.company_name || !form.contact_name || !form.contact_email) return
    setSaving(true)
    try {
      await controlApi.createCarrier({ ...form, driver_count: parseInt(form.driver_count) || 0, status: 'pending' })
      show('Carrier added — pending approval')
      onSaved()
    } catch (err: any) { show(err.message, false) }
    finally { setSaving(false) }
  }

  return (
    <Modal title="Add Carrier" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <label className="block text-xs font-medium text-gray-500 mb-1">Company Name *</label>
            <input required value={form.company_name} onChange={e => set('company_name', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">DOT Number</label>
            <input value={form.dot_number} onChange={e => set('dot_number', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">MC Number</label>
            <input value={form.mc_number} onChange={e => set('mc_number', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Contact Name *</label>
            <input required value={form.contact_name} onChange={e => set('contact_name', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Contact Email *</label>
            <input required type="email" value={form.contact_email} onChange={e => set('contact_email', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Contact Phone</label>
            <input value={form.contact_phone} onChange={e => set('contact_phone', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">State</label>
            <input value={form.state} onChange={e => set('state', e.target.value)} maxLength={2}
              placeholder="TX" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Driver Count</label>
            <input type="number" value={form.driver_count} onChange={e => set('driver_count', e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
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
          {saving ? 'Saving…' : 'Add Carrier (Pending Approval)'}
        </button>
      </form>
    </Modal>
  )
}

export default function CpCarriersTab() {
  const [carriers, setCarriers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [filter, setFilter] = useState('all')
  const [showAdd, setShowAdd] = useState(false)
  const { show, el: toastEl } = useToast()

  const load = useCallback(() => {
    setLoading(true)
    controlApi.listCarriers().then(r => setCarriers(r.carriers ?? [])).catch(e => setErr(e.message)).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const handleStatus = useCallback(async (id: string, status: string) => {
    try { await controlApi.updateCarrier(id, { status }); show(`Carrier ${status}`); load() }
    catch (e: any) { show(e.message, false) }
  }, [load, show])

  const handleRemove = useCallback(async (id: string) => {
    if (!confirm('Remove this carrier?')) return
    try { await controlApi.removeCarrier(id); show('Carrier removed'); load() }
    catch (e: any) { show(e.message, false) }
  }, [load, show])

  const filtered = carriers.filter(c => filter === 'all' || c.status === filter)
  const pendingCount = carriers.filter(c => c.status === 'pending').length

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
          + Add Carrier
        </button>
      </div>

      {loading && <Spinner />}
      {err && <Err msg={err} />}
      {!loading && !err && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: B.offWhite }}>
                {['Company', 'DOT #', 'Contact', 'Phone', 'State', 'Drivers', 'Status', ''].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">No carriers</td></tr>
              )}
              {filtered.map(c => (
                <tr key={c.carrier_id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-800">{c.company_name}</td>
                  <td className="px-4 py-3 text-gray-500 font-mono text-xs">{c.dot_number || '—'}</td>
                  <td className="px-4 py-3">
                    <div className="text-gray-700">{c.contact_name}</div>
                    <div className="text-xs text-gray-400">{c.contact_email}</div>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{c.contact_phone || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{c.state || '—'}</td>
                  <td className="px-4 py-3 text-gray-700">{c.driver_count ?? 0}</td>
                  <td className="px-4 py-3"><Badge status={c.status || 'pending'} /></td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1.5 flex-wrap">
                      {c.status === 'pending' && (
                        <>
                          <button onClick={() => handleStatus(c.carrier_id, 'active')}
                            className="text-xs px-2.5 py-1 rounded-lg bg-green-50 text-green-600 font-medium hover:bg-green-100">Approve</button>
                          <button onClick={() => handleStatus(c.carrier_id, 'inactive')}
                            className="text-xs px-2.5 py-1 rounded-lg bg-red-50 text-red-500 font-medium hover:bg-red-100">Deny</button>
                        </>
                      )}
                      {c.status === 'active' && (
                        <button onClick={() => handleStatus(c.carrier_id, 'inactive')}
                          className="text-xs px-2.5 py-1 rounded-lg bg-gray-100 text-gray-500 font-medium hover:bg-gray-200">Deactivate</button>
                      )}
                      {c.status !== 'removed' && (
                        <button onClick={() => handleRemove(c.carrier_id)}
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

      {showAdd && <AddCarrierModal onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); load() }} show={show} />}
    </div>
  )
}
