import { useCallback, useEffect, useState } from 'react'
import { adminApi } from '../api/admin'
import { BRAND, CONF_COLOR, PASS_COLORS } from '../shared/brandTokens'
import { Spinner } from '../shared/SharedComponents'

export default function FieldsTab({ days: _days }: { days: number }) {
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
            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
            style={sortBy === s ? { background: BRAND.teal, color: BRAND.inkDeep, fontWeight: 700 } : { background: '#F3F4F6', color: '#4B5563' }}
          >{s.replace('_', ' ')}</button>
        ))}
        {data && <span className="text-xs text-gray-400 ml-auto">{data.sample_size} approved scans</span>}
      </div>

      {!data ? <Spinner /> : (
        <>
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
                  <tr key={f.field} onClick={() => openDrill(f.field)}
                    className="cursor-pointer transition-colors hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs font-medium" style={{ color: BRAND.ink }}>{f.field}</td>
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
                        <span style={{ color: BRAND.teal }}>+{(f.pass2_improvement_rate * 100).toFixed(0)}%</span>
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

          {drillField && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-bold font-mono" style={{ color: BRAND.ink }}>{drillField}</h3>
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
                            style={{ background: ((PASS_COLORS as any)[c.pass_status] ?? '#94a3b8') + '20', color: (PASS_COLORS as any)[c.pass_status] ?? '#94a3b8' }}>
                            {c.pass_status}
                          </span>
                        </td>
                        <td className="px-3 py-2 font-medium max-w-[140px] truncate" style={{ color: BRAND.ink }}>{c.ai_value || <span className="text-gray-300 italic">empty</span>}</td>
                        <td className="px-3 py-2 max-w-[140px] truncate" style={{ color: BRAND.teal }}>{c.final_value !== c.ai_value ? c.final_value : '—'}</td>
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
