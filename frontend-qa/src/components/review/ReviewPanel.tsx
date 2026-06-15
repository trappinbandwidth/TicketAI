import { useRef, useState } from 'react'
import type { ProcessResponse, DocumentResult, FieldValue } from '../../types/ticket'
import { DOC_TYPE_FIELDS, FIELD_LABELS } from '../../types/ticket'
import { approveItem, rejectItem } from '../../api/client'
import PassStatusBanner from './PassStatusBanner'
import DocumentViewer, { type DocumentViewerHandle } from './DocumentViewer'
import FieldCard from './FieldCard'
import CdlImpactCard from './CdlImpactCard'
import DocSeverityCard from './DocSeverityCard'
import PriceCard from './PriceCard'
import ActionBar from './ActionBar'

interface Props {
  data: ProcessResponse
  imageB64: string
  onDone: () => void
}

type FeedbackMap = Record<string, 'correct' | 'wrong' | null>

export default function ReviewPanel({ data, imageB64, onDone }: Props) {
  const [editedValues, setEditedValues] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null)
  const [activeField, setActiveField] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<FeedbackMap>({})

  const viewerRef = useRef<DocumentViewerHandle>(null)
  const fieldPanelRef = useRef<HTMLDivElement>(null)

  const queueId = data.queue_id ?? ''
  const fileType = data.result.file_type || 'Ticket'
  const fieldKeys = DOC_TYPE_FIELDS[fileType] ?? DOC_TYPE_FIELDS['Ticket']

  function showToast(msg: string, type: 'success' | 'error') {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  function handleFieldChange(key: string, value: string) {
    setEditedValues(prev => ({ ...prev, [key]: value }))
    // Auto-mark as wrong when human edits a field
    setFeedback(prev => ({ ...prev, [key]: 'wrong' }))
  }

  // Field card zoom button clicked → zoom document to that field
  function handleZoomToField(fieldKey: string) {
    setActiveField(fieldKey)
    viewerRef.current?.zoomToField(fieldKey)
  }

  // Numbered badge on document clicked → scroll to + highlight field card
  function handleBadgeClick(fieldKey: string) {
    setActiveField(fieldKey)
    const el = document.getElementById(`field-${fieldKey}`)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }

  function handleMarkCorrect(key: string) {
    setFeedback(prev => ({ ...prev, [key]: 'correct' }))
  }

  function handleMarkWrong(key: string) {
    setFeedback(prev => ({ ...prev, [key]: 'wrong' }))
  }

  async function handleApprove() {
    if (!queueId) return
    setSaving(true)
    try {
      await approveItem(queueId, editedValues)
      showToast('Approved and saved to training data ✓', 'success')
      setTimeout(onDone, 1500)
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Approve failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleReject(reason: string) {
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
  }

  const lowSet = new Set(data.low_confidence_fields)
  const editCount = Object.keys(editedValues).length
  const correctCount = Object.values(feedback).filter(v => v === 'correct').length
  const wrongCount = Object.values(feedback).filter(v => v === 'wrong').length
  const result = data.result as DocumentResult & Record<string, unknown>

  return (
    <div className="relative">
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-xl shadow-lg text-white font-medium ${toast.type === 'success' ? 'bg-green-500' : 'bg-red-500'}`}>
          {toast.msg}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 p-4">
        {/* Left: document viewer with overlays */}
        <div className="flex flex-col gap-4 sticky top-4 self-start">
          <DocumentViewer
            ref={viewerRef}
            imageB64={imageB64}
            filename={data.filename}
            result={data.result}
            activeField={activeField}
            onFieldBadgeClick={handleBadgeClick}
          />
          <div className="text-xs text-gray-400 text-center">
            {data.pages_processed} page{data.pages_processed !== 1 ? 's' : ''} · {data.mock ? 'MOCK' : 'Live AI'}
            {data.no_attorney_flag && <span className="ml-2 text-amber-500">⚠ No attorney on file</span>}
          </div>

          {/* Feedback summary */}
          {(correctCount > 0 || wrongCount > 0) && (
            <div className="bg-white border border-gray-200 rounded-xl px-4 py-3 flex gap-4 text-sm">
              <span className="text-green-600 font-medium">✓ {correctCount} correct</span>
              <span className="text-red-500 font-medium">✗ {wrongCount} wrong</span>
              <span className="text-gray-400 ml-auto">{editCount} edited</span>
            </div>
          )}

          {/* Attorney matches */}
          {data.attorney_matches && data.attorney_matches.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Matched Attorneys</p>
              <div className="space-y-2">
                {data.attorney_matches.slice(0, 3).map(a => (
                  <div key={a.attorney_id} className="flex items-center justify-between text-sm">
                    <div>
                      <span className="font-medium text-gray-800">{a.name}</span>
                      <span className={`ml-2 text-xs px-1.5 py-0.5 rounded-full ${a.match_type === 'county' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>
                        {a.match_type}
                      </span>
                    </div>
                    <span className="text-gray-500">{Math.round(a.win_rate * 100)}% win</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: extraction results */}
        <div ref={fieldPanelRef} className="flex flex-col gap-4">
          {/* Price — tickets only */}
          {data.price_estimate && fileType === 'Ticket' && (
            <PriceCard estimate={data.price_estimate} />
          )}

          <PassStatusBanner
            status={data.pass_status}
            notes={data.referee_notes}
            escalationReason={data.escalation_reason}
          />

          {/* CDL point impact — tickets only */}
          {data.cdl_point_impact && fileType === 'Ticket' && (
            <CdlImpactCard impact={data.cdl_point_impact} />
          )}

          {/* Doc severity — non-ticket types */}
          {data.doc_severity && (
            <DocSeverityCard severity={data.doc_severity} />
          )}

          {/* Doc type badge */}
          <div className="bg-gray-50 rounded-xl p-3">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Document Type</h3>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-gray-800">{fileType}</span>
              <span className={`text-xs px-2 py-0.5 rounded-full ${result.document_text_format === 'digital' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                {result.document_text_format}
              </span>
            </div>
            {result.file_type_analysis?.ai_reason && (
              <p className="text-xs text-gray-400 mt-1">{result.file_type_analysis.ai_reason}</p>
            )}
            {data.dual_conflicts.length > 0 && (
              <p className="text-xs text-amber-600 mt-1">⚠ Conflicts: {data.dual_conflicts.join(', ')}</p>
            )}
          </div>

          {/* Extracted fields */}
          <div>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3 px-1">
              Extracted Fields
              {lowSet.size > 0 && (
                <span className="ml-2 text-red-500 normal-case font-normal">{lowSet.size} low-confidence</span>
              )}
              <span className="ml-2 text-gray-400 normal-case font-normal text-[10px]">
                Click 🔍 to jump to field on document · Click value to edit
              </span>
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {fieldKeys.map(key => {
                const field = result[key as string]
                if (!field || typeof field !== 'object' || !('value' in (field as object))) return null
                const fv = field as FieldValue
                if (!fv.value && fv.confidence_score === 0) return null
                return (
                  <FieldCard
                    key={key as string}
                    fieldKey={key as string}
                    label={FIELD_LABELS[key as string] ?? key as string}
                    field={fv}
                    isLowConfidence={lowSet.has(key as string)}
                    editedValue={editedValues[key as string]}
                    onChange={handleFieldChange}
                    isActive={activeField === key}
                    onZoom={handleZoomToField}
                    feedbackState={feedback[key as string] ?? null}
                    onMarkCorrect={handleMarkCorrect}
                    onMarkWrong={handleMarkWrong}
                  />
                )
              })}
            </div>
          </div>

          <ActionBar
            onApprove={handleApprove}
            onReject={handleReject}
            loading={saving}
            editCount={editCount}
          />
        </div>
      </div>
    </div>
  )
}
