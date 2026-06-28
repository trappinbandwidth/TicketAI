import { useEffect, useState } from 'react'
import { adminApi } from '../api/admin'
import { BRAND, PASS_COLORS } from '../shared/brandTokens'
import { Spinner } from '../shared/SharedComponents'

export default function ScanFeedTab() {
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
              <td className="px-4 py-3 text-xs text-gray-400 font-mono">{s.created_at?.slice(11, 16)}</td>
              <td className="px-4 py-3 text-xs font-medium max-w-[160px] truncate" style={{ color: BRAND.ink }}>{s.filename}</td>
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
                  ? <span style={{ color: BRAND.tealDark }}>✓ {s.attorney_match_type}</span>
                  : <span className="text-gray-300">—</span>}
              </td>
              <td className="px-4 py-3 text-xs">
                {s.has_price_estimate
                  ? <span style={{ color: BRAND.teal }}>✓</span>
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
