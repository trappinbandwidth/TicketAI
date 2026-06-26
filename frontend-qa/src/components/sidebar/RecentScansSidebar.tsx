import { useState, useEffect } from 'react'
import type { QueueSummary } from '../../types/ticket'
import { listQueue, getQueueItem, approveItem } from '../../api/client'

const TEAL = '#2EC4A5'
const INK  = '#2D3142'

const PASS_DOT: Record<string, string> = {
  green: 'bg-green-500', yellow: 'bg-yellow-400', red: 'bg-red-500',
}
const PASS_LABEL: Record<string, string> = {
  green: 'GREEN', yellow: 'YELLOW', red: 'RED',
}
const STATUS_STYLE: Record<string, string> = {
  approved: 'bg-green-50 text-green-700',
  rejected: 'bg-red-50 text-red-600',
  pending:  'bg-yellow-50 text-yellow-700',
}

type PassFilter   = 'all' | 'green' | 'yellow' | 'red'
type StatusFilter = 'all' | 'pending' | 'approved' | 'rejected'

interface Props {
  onLoadItem: (item: { data: import('../../types/ticket').ProcessResponse; pages: string[]; imageB64: string }) => void
  refreshTick: number
}

export default function RecentScansSidebar({ onLoadItem, refreshTick }: Props) {
  const [items, setItems] = useState<QueueSummary[]>([])
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [bulkBusy, setBulkBusy] = useState(false)
  const [passFilter, setPassFilter]     = useState<PassFilter>('all')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')

  async function refresh() {
    try {
      setItems(await listQueue())
    } catch { /* ignore */ }
  }

  useEffect(() => { refresh() }, [refreshTick])
  useEffect(() => {
    const id = setInterval(refresh, 15_000)
    return () => clearInterval(id)
  }, [])

  async function loadItem(id: string) {
    setLoadingId(id)
    try {
      const item = await getQueueItem(id)
      const pages = item.images_all?.length > 0 ? item.images_all : (item.image_b64 ? [item.image_b64] : [])
      onLoadItem({ data: item.process_response, pages, imageB64: pages[0] ?? '' })
    } catch { /* ignore */ }
    finally { setLoadingId(null) }
  }

  async function bulkApproveGreens() {
    const greens = items.filter(i => i.pass_status === 'green' && i.status === 'pending')
    if (!greens.length) return
    if (!confirm(`Approve all ${greens.length} pending GREEN scan(s) with no edits?`)) return
    setBulkBusy(true)
    let done = 0
    for (const g of greens) {
      try { await approveItem(g.id, {}); done++ } catch { /* ignore */ }
    }
    setBulkBusy(false)
    refresh()
    alert(`Bulk approved ${done} GREEN scan${done !== 1 ? 's' : ''}.`)
  }

  // Filter + sort
  const filtered = items
    .filter(i => passFilter === 'all'   || i.pass_status === passFilter)
    .filter(i => statusFilter === 'all' || i.status === statusFilter)
    .sort((a, b) => {
      const pri = (i: QueueSummary) =>
        i.status === 'pending' && i.pass_status === 'red' ? 0
        : i.status === 'pending' ? 1 : 2
      return pri(a) - pri(b)
    })
    .slice(0, 50)

  const pending  = items.filter(i => i.status === 'pending').length
  const redCount = items.filter(i => i.pass_status === 'red' && i.status === 'pending').length
  const approved = items.filter(i => i.status === 'approved').length
  const greens   = items.filter(i => i.pass_status === 'green' && i.status === 'pending').length

  function FilterTab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
    return (
      <button
        onClick={onClick}
        className="text-[11px] font-semibold px-2 py-0.5 rounded transition-all"
        style={active
          ? { background: TEAL, color: INK }
          : { background: '#f1f5f9', color: '#475569' }}
      >{label}</button>
    )
  }

  if (items.length === 0) return null

  return (
    <div className="w-72 shrink-0 border-l border-gray-200 bg-white overflow-hidden flex flex-col">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-slate-100 flex items-center justify-between flex-shrink-0"
        style={{ background: INK }}>
        <div>
          <p className="text-white text-xs font-bold uppercase tracking-widest">Recent Scans</p>
          <p className="text-xs mt-0.5" style={{ color: '#64748b' }}>
            {pending} pending{redCount ? ` · ${redCount} red` : ''} · {approved} approved
          </p>
        </div>
        <div className="flex items-center gap-2">
          {greens > 0 && (
            <button
              onClick={bulkApproveGreens}
              disabled={bulkBusy}
              className="text-xs font-semibold px-2 py-1 rounded transition-all disabled:opacity-50"
              style={{ background: 'rgba(255,255,255,.12)', color: '#d1fae5' }}
              title="Approve all pending GREEN scans"
            >
              {bulkBusy ? '…' : `⚡ Bulk (${greens})`}
            </button>
          )}
          <button onClick={refresh} className="text-slate-400 hover:text-white text-sm transition-colors" title="Refresh">↻</button>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="px-3 py-2 border-b border-slate-100 space-y-1.5 flex-shrink-0">
        <div className="flex gap-1 flex-wrap">
          <FilterTab label="All"    active={passFilter === 'all'}    onClick={() => setPassFilter('all')} />
          <FilterTab label="🟢 Green"  active={passFilter === 'green'}  onClick={() => setPassFilter('green')} />
          <FilterTab label="🟡 Yellow" active={passFilter === 'yellow'} onClick={() => setPassFilter('yellow')} />
          <FilterTab label="🔴 Red"    active={passFilter === 'red'}    onClick={() => setPassFilter('red')} />
        </div>
        <div className="flex gap-1 flex-wrap">
          <FilterTab label="All"      active={statusFilter === 'all'}      onClick={() => setStatusFilter('all')} />
          <FilterTab label="Pending"  active={statusFilter === 'pending'}  onClick={() => setStatusFilter('pending')} />
          <FilterTab label="Approved" active={statusFilter === 'approved'} onClick={() => setStatusFilter('approved')} />
          <FilterTab label="Rejected" active={statusFilter === 'rejected'} onClick={() => setStatusFilter('rejected')} />
        </div>
      </div>

      {/* List */}
      <ul className="divide-y divide-slate-100 overflow-y-auto flex-1">
        {filtered.length === 0 && (
          <li className="px-4 py-6 text-xs text-slate-400 text-center">No results.</li>
        )}
        {filtered.map(item => {
          const dot = PASS_DOT[item.pass_status] ?? 'bg-gray-400'
          const lbl = PASS_LABEL[item.pass_status] ?? item.pass_status.toUpperCase()
          const sty = STATUS_STYLE[item.status] ?? 'bg-gray-50 text-gray-500'
          return (
            <li
              key={item.id}
              className="px-3 py-2.5 hover:bg-slate-50 cursor-pointer transition-colors"
              onClick={() => loadItem(item.id)}
            >
              {loadingId === item.id ? (
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <span className="w-3 h-3 border border-slate-400 border-t-transparent rounded-full animate-spin" />
                  Loading…
                </div>
              ) : (
                <>
                  <p className="text-xs font-semibold text-slate-700 truncate leading-snug">{item.filename}</p>
                  <div className="flex items-center gap-1.5 mt-1">
                    <span className={`text-white text-[10px] font-bold px-1.5 py-0.5 rounded-sm ${dot.replace('bg-', 'bg-')}`}
                      style={{ background: item.pass_status === 'green' ? '#16a34a' : item.pass_status === 'yellow' ? '#ca8a04' : '#dc2626' }}>
                      {lbl}
                    </span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-sm ${sty}`}>{item.status}</span>
                    <span className="text-[10px] text-slate-400 ml-auto">
                      {new Date(item.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
