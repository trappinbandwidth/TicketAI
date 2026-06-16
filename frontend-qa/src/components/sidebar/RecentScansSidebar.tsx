import { useState, useEffect } from 'react'
import type { QueueSummary } from '../../types/ticket'
import { listQueue, getQueueItem } from '../../api/client'
import { passStatusColors, statusBadge } from '../../utils/confidence'

interface Props {
  onLoadItem: (item: { data: import('../../types/ticket').ProcessResponse; pages: string[]; imageB64: string }) => void
  refreshTick: number
}

export default function RecentScansSidebar({ onLoadItem, refreshTick }: Props) {
  const [items, setItems] = useState<QueueSummary[]>([])
  const [loadingId, setLoadingId] = useState<string | null>(null)

  async function refresh() {
    try {
      const data = await listQueue()
      setItems(data.slice(0, 20))
    } catch {
      // silently ignore
    }
  }

  useEffect(() => {
    refresh()
  }, [refreshTick])

  useEffect(() => {
    const id = setInterval(refresh, 15000)
    return () => clearInterval(id)
  }, [])

  async function loadItem(id: string) {
    setLoadingId(id)
    try {
      const item = await getQueueItem(id)
      const pages = item.images_all?.length > 0 ? item.images_all : (item.image_b64 ? [item.image_b64] : [])
      onLoadItem({ data: item.process_response, pages, imageB64: pages[0] ?? '' })
    } catch {
      // silently ignore
    } finally {
      setLoadingId(null)
    }
  }

  if (items.length === 0) return null

  return (
    <div className="w-72 shrink-0 border-l border-gray-200 bg-white overflow-y-auto">
      <div className="px-4 py-3 border-b border-gray-100">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Recent Scans</h2>
      </div>
      <ul className="divide-y divide-gray-100">
        {items.map(item => {
          const ps = passStatusColors(item.pass_status)
          const sb = statusBadge(item.status)
          return (
            <li
              key={item.id}
              className="px-4 py-3 hover:bg-gray-50 cursor-pointer group"
              onClick={() => loadItem(item.id)}
            >
              {loadingId === item.id ? (
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <span className="w-3 h-3 border border-gray-400 border-t-transparent rounded-full animate-spin" />
                  Loading…
                </div>
              ) : (
                <>
                  <p className="text-sm font-medium text-gray-700 truncate group-hover:text-blue-600">
                    {item.filename}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-xs px-1.5 py-0.5 rounded font-bold text-white ${ps.bg}`}>
                      {ps.label}
                    </span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${sb.bg} ${sb.text}`}>
                      {item.status}
                    </span>
                    <span className="text-xs text-gray-400 ml-auto">
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
