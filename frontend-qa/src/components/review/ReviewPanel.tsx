import { useRef, useState, useEffect, useCallback } from 'react'
import type { ProcessResponse, DocumentResult, FieldValue } from '../../types/ticket'
import { DOC_TYPE_FIELDS, FIELD_LABELS } from '../../types/ticket'
import { approveItem, rejectItem, getAuditTrail } from '../../api/client'
import PassStatusBanner from './PassStatusBanner'
import DocumentViewer, { type DocumentViewerHandle } from './DocumentViewer'
import FieldCard from './FieldCard'
import CdlImpactCard from './CdlImpactCard'
import DocSeverityCard from './DocSeverityCard'
import PriceCard from './PriceCard'
import ActionBar from './ActionBar'

const TEAL     = '#2EC4A5'
const TEAL_DRK = '#1E9E85'
const INK      = '#2D3142'

// PII fields to surface in the driver info card
const PII_FIELD_MAP = [
  { key: 'Driver_First_Name__c',  label: 'First Name' },
  { key: 'Driver_Last_Name__c',   label: 'Last Name' },
  { key: 'CDL_License_Number__c', label: 'CDL #' },
  { key: 'MVR_License_Number__c', label: 'License #' },
  { key: 'CDL_Class__c',          label: 'CDL Class' },
  { key: 'CDL_State__c',          label: 'State' },
  { key: 'Driver_DOB__c',         label: 'DOB' },
  { key: 'CDL_Expiration__c',     label: 'CDL Exp.' },
  { key: 'Unit_License_Plate__c', label: 'Plate #' },
  { key: 'DOT_Number__c',         label: 'DOT #' },
  { key: 'VIN__c',                label: 'VIN' },
  { key: 'Driver_Address__c',     label: 'Address' },
] as const

const MEDALS = ['🥇', '🥈', '🥉']

interface Props {
  data: ProcessResponse
  pages: string[]
  imageB64: string
  onDone: () => void
}

export default function ReviewPanel({ data, pages, imageB64, onDone }: Props) {
  const [editedValues, setEditedValues]   = useState<Record<string, string>>({})
  const [saving, setSaving]               = useState(false)
  const [toast, setToast]                 = useState<{ msg: string; type: 'success' | 'error' } | null>(null)
  const [activeField, setActiveField]     = useState<string | null>(null)
  const [problemsOnly, setProblemsOnly]   = useState(false)
  const [auditEntries, setAuditEntries]   = useState<any[]>([])
  const [auditLoaded, setAuditLoaded]     = useState(false)

  const viewerRef    = useRef<DocumentViewerHandle>(null)
  const fieldPaneRef = useRef<HTMLDivElement>(null)

  const queueId  = data.queue_id ?? ''
  const fileType = data.result.file_type || 'Ticket'
  const result   = data.result as DocumentResult & Record<string, unknown>

  const lowSet      = new Set(data.low_confidence_fields)
  const conflictSet = new Set(data.dual_conflicts)
  const editCount   = Object.keys(editedValues).length

  // Field sort: conflicts first → low-conf → doc-type order
  const baseKeys = (DOC_TYPE_FIELDS[fileType] ?? DOC_TYPE_FIELDS['Ticket']) as string[]
  const sortedFieldKeys = [...baseKeys].sort((a, b) => {
    const rank = (k: string) => conflictSet.has(k) ? 0 : lowSet.has(k) ? 1 : 2
    return rank(a) - rank(b)
  })

  function showToast(msg: string, type: 'success' | 'error') {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  function handleFieldChange(key: string, value: string) {
    setEditedValues(prev => ({ ...prev, [key]: value }))
  }

  function handleZoomToField(fieldKey: string) {
    setActiveField(fieldKey)
    viewerRef.current?.zoomToField(fieldKey)
  }

  function handleBadgeClick(fieldKey: string) {
    setActiveField(fieldKey)
    const el = document.getElementById(`field-${fieldKey}`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const handleApprove = useCallback(async () => {
    if (!queueId) return
    setSaving(true)
    try {
      await approveItem(queueId, editedValues)
      // Load audit trail before confirming
      const entries = await getAuditTrail(queueId).catch(() => [])
      setAuditEntries(entries)
      setAuditLoaded(true)
      showToast('Approved and saved to training data ✓', 'success')
      setTimeout(onDone, 1500)
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Approve failed', 'error')
    } finally {
      setSaving(false)
    }
  }, [queueId, editedValues, onDone])

  const handleReject = useCallback(async (reason: string) => {
    if (!queueId) return
    setSaving(true)
    try {
      await rejectItem(queueId, reason)
      showToast('Document rejected', 'success')
      setTimeout(onDone, 1500)
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Reject failed', 'error')
    } finally {
      setSaving(false)
    }
  }, [queueId, onDone])

  // Load audit trail on mount
  useEffect(() => {
    if (!queueId) return
    getAuditTrail(queueId).then(entries => {
      setAuditEntries(entries)
      setAuditLoaded(true)
    }).catch(() => { setAuditLoaded(true) })
  }, [queueId])

  // Keyboard shortcuts (G=approve, R=reject focus, P=problems-only)
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (document.activeElement as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return
      if (e.ctrlKey || e.metaKey || e.altKey) return
      if (e.key === 'g' || e.key === 'G') { e.preventDefault(); handleApprove() }
      if (e.key === 'p' || e.key === 'P') { e.preventDefault(); setProblemsOnly(p => !p) }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [handleApprove])

  // PII badges
  const piiBadges = PII_FIELD_MAP
    .filter(({ key }) => (result[key] as FieldValue | undefined)?.value?.trim())
    .map(({ key, label }) => ({ key, label, field: result[key] as FieldValue }))

  return (
    <div className="relative">
      {/* Toast */}
      {toast && (
        <div
          className="fixed top-4 right-4 z-50 px-4 py-3 rounded-xl shadow-lg font-semibold text-sm"
          style={toast.type === 'success' ? { background: TEAL, color: INK } : { background: '#DC2626', color: '#fff' }}
        >
          {toast.msg}
        </div>
      )}

      {/* Status bar — full width above split */}
      <div className="mx-4 mt-4 mb-0 bg-white border border-gray-200 rounded-xl px-4 py-3 flex flex-wrap items-center gap-4">
        <PassStatusBanner
          status={data.pass_status}
          notes={data.referee_notes}
          escalationReason={data.escalation_reason}
        />
        <div className="ml-auto flex items-center gap-3">
          <button
            onClick={() => setProblemsOnly(p => !p)}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg border transition-all"
            style={problemsOnly
              ? { background: '#F59E0B', color: '#fff', borderColor: '#F59E0B' }
              : { background: '#f8fafc', color: '#64748b', borderColor: '#e2e8f0' }}
            title="P"
          >
            ⚠ Problems only{problemsOnly ? ' (on)' : ''}
          </button>
          <div className="text-right">
            <div className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Pages</div>
            <span className="text-xl font-bold" style={{ color: TEAL }}>{data.pages_processed ?? '—'}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 p-4">

        {/* ── LEFT: sticky image pane ───────────────────────────────── */}
        <div className="flex flex-col gap-4" style={{ position: 'sticky', top: 16, alignSelf: 'start' }}>
          <DocumentViewer
            ref={viewerRef}
            pages={pages}
            imageB64={imageB64}
            filename={data.filename}
            result={data.result}
            activeField={activeField}
            onFieldBadgeClick={handleBadgeClick}
          />

          {/* PII card */}
          {piiBadges.length > 0 && (
            <div className="bg-white rounded-xl border-l-4 border border-gray-200 p-4"
              style={{ borderLeftColor: TEAL }}>
              <div className="flex items-center justify-between mb-2">
                <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Driver Information (PII)</p>
                <span className="text-[10px] text-slate-400">Click a field to highlight on document</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {piiBadges.map(({ key, label, field }) => (
                  <button
                    key={key}
                    onClick={() => field.bbox ? handleZoomToField(key) : undefined}
                    className="flex items-center gap-1.5 px-2 py-1 rounded-lg border text-xs transition-all"
                    style={{ background: '#eff6ff', borderColor: '#bfdbfe', cursor: field.bbox ? 'pointer' : 'default' }}
                    title={field.bbox ? `Click to highlight ${label} on document` : label}
                  >
                    <span className="text-slate-500">{label}:</span>
                    <span className="font-bold" style={{ color: INK }}>{field.value}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Price */}
          {data.price_estimate && fileType === 'Ticket' && (
            <PriceCard estimate={data.price_estimate} />
          )}

          {/* Attorney matches */}
          {data.attorney_matches && data.attorney_matches.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500 mb-3">Suggested Attorneys</p>
              {data.no_attorney_flag && data.attorney_matches.length === 0 ? (
                <p className="text-sm font-semibold text-red-600">⚠ No Attorney on File — team alert required.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {data.attorney_matches.slice(0, 3).map((a, i) => {
                    const medal = MEDALS[i] ?? `#${i + 1}`
                    const winPct = a.win_rate > 0 ? `${Math.round(a.win_rate * 100)}%` : '—'
                    return (
                      <div key={a.attorney_id} className="border border-slate-100 rounded-xl p-3 flex items-start gap-3">
                        <span className="text-xl leading-none mt-0.5">{medal}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-semibold text-sm" style={{ color: INK }}>{a.name}</span>
                            <span
                              className="text-[10px] px-1.5 py-0.5 rounded font-semibold"
                              style={a.match_type === 'county'
                                ? { background: '#dbeafe', color: '#1d4ed8' }
                                : { background: '#f3f4f6', color: '#6b7280' }}
                            >{a.match_type}</span>
                            {a.rating && a.rating > 0 && (
                              <span className="text-xs text-amber-500 font-semibold">★ {a.rating.toFixed(1)}</span>
                            )}
                          </div>
                          <div className="flex gap-3 text-xs text-slate-500 mt-1 flex-wrap">
                            <span>Win: <strong className="text-slate-700">{winPct}</strong></span>
                            {a.total_tickets > 0 && <span>Tickets: <strong className="text-slate-700">{a.total_tickets.toLocaleString()}</strong></span>}
                            {a.phone && <a href={`tel:${a.phone}`} className="hover:underline" style={{ color: TEAL_DRK }}>{a.phone}</a>}
                            {a.email && <a href={`mailto:${a.email}`} className="hover:underline truncate max-w-[160px]" style={{ color: TEAL_DRK }}>{a.email}</a>}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* Keyboard hints */}
          <div className="text-[10px] text-slate-400 flex flex-wrap gap-x-3 gap-y-0.5 px-1">
            <span><kbd className="border border-slate-300 rounded px-1 bg-slate-50 font-mono">G</kbd> Approve</span>
            <span><kbd className="border border-slate-300 rounded px-1 bg-slate-50 font-mono">P</kbd> Problems only</span>
            <span><kbd className="border border-slate-300 rounded px-1 bg-slate-50 font-mono">+/−</kbd> Zoom</span>
            <span><kbd className="border border-slate-300 rounded px-1 bg-slate-50 font-mono">[/]</kbd> Rotate</span>
          </div>
        </div>

        {/* ── RIGHT: fields pane ────────────────────────────────────── */}
        <div ref={fieldPaneRef} className="flex flex-col gap-4">

          {/* CDL / doc severity */}
          {data.cdl_point_impact && fileType === 'Ticket' && (
            <CdlImpactCard impact={data.cdl_point_impact} />
          )}
          {data.doc_severity && (
            <DocSeverityCard severity={data.doc_severity} />
          )}

          {/* Dual-conflict banner */}
          {conflictSet.size > 0 && (
            <div className="rounded-xl border border-violet-300 bg-violet-50 px-4 py-3 flex items-start gap-3">
              <svg className="mt-0.5 shrink-0 text-violet-500" width="16" height="16" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21 3 12l4.5-9h9l4.5 9-4.5 9h-9Z" />
              </svg>
              <div>
                <p className="text-sm font-semibold text-violet-800">Dual-pass conflict — AI disagreed on these fields</p>
                <p className="text-xs text-violet-700 mt-0.5">
                  {[...conflictSet].map(k => FIELD_LABELS[k] ?? k).join(', ')}
                </p>
              </div>
            </div>
          )}

          {/* Low-confidence banner */}
          {lowSet.size > 0 && (
            <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 flex items-start gap-3">
              <svg className="mt-0.5 shrink-0 text-amber-500" width="16" height="16" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
              </svg>
              <div>
                <p className="text-sm font-semibold text-amber-800">Low-confidence fields</p>
                <p className="text-xs text-amber-700 mt-0.5">
                  {[...lowSet].map(k => FIELD_LABELS[k] ?? k).join(', ')}
                </p>
              </div>
            </div>
          )}

          {/* Extracted fields header */}
          <div>
            <div className="flex items-center justify-between mb-2 px-1">
              <h3 className="text-[11px] font-bold uppercase tracking-wide text-slate-500">
                Extracted Fields
                {editCount > 0 && (
                  <span className="ml-2 text-amber-600 normal-case font-semibold">{editCount} edit{editCount > 1 ? 's' : ''} pending</span>
                )}
              </h3>
              {editCount > 0 && (
                <button
                  onClick={() => setEditedValues({})}
                  className="text-xs text-slate-500 hover:text-slate-700 px-2 py-1 rounded hover:bg-slate-100 transition-colors"
                >
                  ↩ Reset edits
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {sortedFieldKeys.map(key => {
                const field = result[key]
                if (!field || typeof field !== 'object' || !('value' in (field as object))) return null
                const fv = field as FieldValue
                if (!fv.value && fv.confidence_score === 0) return null
                const isLow = lowSet.has(key)
                const isConflict = conflictSet.has(key)
                const hide = problemsOnly && !isLow && !isConflict
                return (
                  <FieldCard
                    key={key}
                    fieldKey={key}
                    label={FIELD_LABELS[key] ?? key}
                    field={fv}
                    isLowConfidence={isLow}
                    isConflict={isConflict}
                    editedValue={editedValues[key]}
                    onChange={handleFieldChange}
                    isActive={activeField === key}
                    onZoom={handleZoomToField}
                    hidden={hide}
                  />
                )
              })}
            </div>
          </div>

          {/* Doc metadata */}
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400 mb-2">Document Metadata</p>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div><span className="text-slate-400">Type: </span><span className="font-semibold text-slate-700">{result.file_type || '—'}</span></div>
              <div><span className="text-slate-400">Format: </span><span className="font-semibold text-slate-700">{result.document_text_format || '—'}</span></div>
              {result.file_type_analysis && (
                <div><span className="text-slate-400">Confidence: </span>
                  <span className="font-semibold text-slate-700">{Math.round(result.file_type_analysis.confidence_score * 100)}%</span>
                </div>
              )}
              {(result.other_document_types?.length ?? 0) > 0 && (
                <div className="col-span-2">
                  <span className="text-slate-400">Other types: </span>
                  <span className="font-semibold text-slate-700">{result.other_document_types?.join(', ')}</span>
                </div>
              )}
            </div>
            {result.file_type_analysis?.ai_reason && (
              <p className="text-xs text-slate-400 mt-2 italic leading-snug">{result.file_type_analysis.ai_reason}</p>
            )}
          </div>

          {/* Action bar */}
          <ActionBar
            onApprove={handleApprove}
            onReject={handleReject}
            loading={saving}
            editCount={editCount}
          />

          {/* Audit trail */}
          {auditLoaded && (
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400 mb-3">Review Audit Trail</p>
              {auditEntries.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No audit entries yet.</p>
              ) : (
                <div className="space-y-0">
                  {auditEntries.map((e, i) => {
                    const who   = e.reviewer_id ? ` by ${e.reviewer_id}` : ''
                    const when  = e.timestamp ? new Date(e.timestamp).toLocaleString() : ''
                    const field = e.field_key ? `${FIELD_LABELS[e.field_key] ?? e.field_key}: ` : ''
                    const val   = e.new_value != null ? ` → "${String(e.new_value)}"` : ''
                    return (
                      <div key={i} className="flex gap-2 items-start py-1.5 border-b border-slate-50 last:border-0">
                        <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ background: TEAL }} />
                        <div>
                          <p className="text-xs text-slate-600 leading-snug">
                            {field && <span className="italic">{field}</span>}
                            <strong>{e.action || 'update'}</strong>{val}{who}
                          </p>
                          {when && <p className="text-[10px] text-slate-400 mt-0.5">{when}</p>}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
