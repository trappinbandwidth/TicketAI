import { useCallback, useRef, useState } from 'react'
import { BRAND } from './brandTokens'

export const B = BRAND

export const STAFF = ['Quest', 'Justin', 'Eniola'] as const

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="w-8 h-8 border-2 border-gray-200 rounded-full animate-spin"
        style={{ borderTopColor: B.teal }} />
    </div>
  )
}

export function Err({ msg }: { msg: string }) {
  return <div className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg px-4 py-3">{msg}</div>
}

export function KpiCard({ label, value, sub, color, danger }: {
  label: string; value: string | number; sub?: string; color?: string; danger?: boolean
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-col gap-1"
      style={danger ? { borderColor: '#FCA5A5', background: '#FFF5F5' } : {}}>
      <span className="text-xs font-medium uppercase tracking-wide" style={{ color: '#94A3B8' }}>{label}</span>
      <span className="text-3xl font-black" style={{ color: color ?? B.ink }}>{value}</span>
      {sub && <span className="text-xs" style={{ color: '#94A3B8' }}>{sub}</span>}
    </div>
  )
}

const STATUS_BADGE: Record<string, string> = {
  active:            'bg-green-100 text-green-700',
  approved:          'bg-green-100 text-green-700',
  pending:           'bg-amber-100 text-amber-700',
  pending_approval:  'bg-blue-100 text-blue-700',
  inactive:          'bg-gray-100 text-gray-500',
  cancelled:         'bg-red-100 text-red-600',
  archived:          'bg-gray-200 text-gray-500',
  removed:           'bg-red-100 text-red-500',
  attorney_declined: 'bg-red-100 text-red-600',
  outcome_logged:    'bg-purple-100 text-purple-700',
  payout_sent:       'bg-teal-100 text-teal-700',
  closed:            'bg-gray-100 text-gray-500',
  rejected:          'bg-red-100 text-red-600',
  New:               'bg-blue-100 text-blue-700',
  'Admin Assigned':  'bg-indigo-100 text-indigo-700',
  Accepted:          'bg-green-100 text-green-700',
  'Ticket Closed':   'bg-gray-100 text-gray-500',
  'AI Review':       'bg-yellow-100 text-yellow-700',
  Rejected:          'bg-red-100 text-red-600',
  paused:            'bg-orange-100 text-orange-600',
  silver:            'bg-gray-100 text-gray-600',
  gold:              'bg-yellow-100 text-yellow-700',
  platinum:          'bg-indigo-100 text-indigo-700',
}

export function Badge({ status }: { status: string }) {
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold ${STATUS_BADGE[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)' }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-bold" style={{ color: B.ink }}>{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl font-bold leading-none">×</button>
        </div>
        <div className="overflow-y-auto p-6 flex-1">{children}</div>
      </div>
    </div>
  )
}

export function Drawer({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-40 flex">
      <div className="flex-1" onClick={onClose} style={{ background: 'rgba(0,0,0,0.3)' }} />
      <div className="w-full max-w-2xl bg-white shadow-2xl flex flex-col h-full">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 shrink-0"
          style={{ background: B.ink }}>
          <h2 className="text-base font-bold text-white">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl font-bold leading-none">×</button>
        </div>
        <div className="overflow-y-auto flex-1 p-6">{children}</div>
      </div>
    </div>
  )
}

export function Field({ label, value }: { label: string; value?: string | number | null }) {
  if (value == null || value === '') return null
  return (
    <div>
      <dt className="text-xs font-medium text-gray-400 uppercase tracking-wide">{label}</dt>
      <dd className="text-sm font-medium text-gray-800 mt-0.5">{String(value)}</dd>
    </div>
  )
}

export function FieldGrid({ children }: { children: React.ReactNode }) {
  return <dl className="grid grid-cols-2 gap-3">{children}</dl>
}

export function useToast() {
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const show = useCallback((msg: string, ok = true) => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setToast({ msg, ok })
    timerRef.current = setTimeout(() => setToast(null), 3500)
  }, [])
  const el = toast ? (
    <div className="fixed top-4 right-4 z-[60] px-4 py-3 rounded-xl shadow-lg text-sm font-medium transition-all"
      style={{ background: toast.ok ? B.teal : '#EF4444', color: '#fff' }}>
      {toast.msg}
    </div>
  ) : null
  return { show, el }
}

export function useStaff() {
  const [staff, setStaffState] = useState<string>(() => localStorage.getItem('rr_reviewer') || 'Quest')
  const setStaff = (s: string) => { setStaffState(s); localStorage.setItem('rr_reviewer', s) }
  return { staff, setStaff }
}
