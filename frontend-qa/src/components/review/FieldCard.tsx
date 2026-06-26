import { useState } from 'react'
import type { FieldValue } from '../../types/ticket'

// ── Smart input metadata (mirrors frontend/index.html exactly) ───────────────
const DATE_FIELDS = new Set([
  'Date_of_Ticket__c', 'Court_Date__c',
  'Inspection_Date__c', 'Crash_Date__c',
  'Civil_Penalty_Due_Date__c', 'CDL_Expiration__c',
  'Driver_DOB__c', 'MVR_Generated_Date__c',
])

const VIOLATION_CATEGORIES = [
  '',
  'Driver license violation',
  'Alcohol / Drug related violation',
  'Reckless Driving',
  'Speeding (15+)',
  'Cell Phone',
  'Failure to yield to emergency vehicle',
  'Following too close',
  'Careless Driving',
  'Lane Violation',
  'Failure to Obey Traffic Control Device',
  'Too Fast for Conditions',
  'Speeding (1-14)',
  'Seatbelt',
  'ELD/Logs',
  'Equipment/Maintenance',
  'Registration Violations',
  'Overweight/Overlength',
  'Parking',
]

const SELECT_FIELDS: Record<string, string[]> = {
  Violation_Category__c: VIOLATION_CATEGORIES,
}

const YESNO_FIELDS = new Set([
  'Accident__c', 'Driver_OOS__c', 'Vehicle_OOS__c',
  'Federal_Recordable__c', 'State_Reportable__c',
  'Towaway__c', 'Citation_Issued__c', 'HM_Involved__c',
])

function mmddyyyyToIso(v: string): string {
  const m = v?.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/)
  if (!m) return ''
  return `${m[3]}-${m[1].padStart(2, '0')}-${m[2].padStart(2, '0')}`
}

function isoToMmddyyyy(v: string): string {
  const m = v?.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return v
  return `${m[2]}/${m[3]}/${m[1]}`
}

interface Props {
  fieldKey: string
  label?: string
  field: FieldValue
  isLowConfidence: boolean
  isConflict?: boolean
  editedValue?: string
  onChange: (key: string, value: string) => void
  isActive?: boolean
  onZoom?: (key: string) => void
  hidden?: boolean
  feedbackState?: 'correct' | 'wrong' | null
  onMarkCorrect?: (key: string) => void
  onMarkWrong?: (key: string) => void
}

export default function FieldCard({
  fieldKey, label, field, isLowConfidence, isConflict = false,
  editedValue, onChange, isActive, onZoom, hidden = false,
  feedbackState, onMarkCorrect, onMarkWrong,
}: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')

  const displayValue = editedValue !== undefined ? editedValue : field.value
  const isEdited = editedValue !== undefined && editedValue !== field.value
  const hasBbox = !!field.bbox
  const conf = field.confidence_score ?? 0
  const pct = Math.round(conf * 100)

  const barColor = conf >= 0.85 ? '#22c55e' : conf >= 0.60 ? '#f59e0b' : '#ef4444'
  const pctColor = conf >= 0.85 ? 'text-green-600' : conf >= 0.60 ? 'text-amber-600' : 'text-red-500'

  // Left-border color coding (same as vanilla HTML)
  let borderLeft = '4px solid #22c55e'   // ok-conf = green
  if (isConflict) borderLeft = '4px solid #8b5cf6'        // conflict = purple
  else if (isLowConfidence) borderLeft = '4px solid #f59e0b' // low-conf = amber

  // Active/edited top border
  let ringColor = ''
  if (isActive) ringColor = 'ring-2 ring-blue-300'
  else if (isEdited) ringColor = 'ring-2 ring-amber-300'

  function startEdit() {
    const raw = editedValue !== undefined ? editedValue : field.value
    if (DATE_FIELDS.has(fieldKey)) {
      setDraft(mmddyyyyToIso(raw))
    } else {
      setDraft(raw)
    }
    setEditing(true)
  }

  function commitEdit() {
    let val = draft
    if (DATE_FIELDS.has(fieldKey)) {
      val = isoToMmddyyyy(draft)
    }
    onChange(fieldKey, val)
    setEditing(false)
  }

  if (hidden) return null

  return (
    <div
      id={`field-${fieldKey}`}
      className={`bg-slate-50 rounded-xl border border-slate-100 p-3 transition-shadow hover:shadow-md ${ringColor}`}
      style={{ borderLeft }}
    >
      {/* Header row */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-bold uppercase tracking-wide text-slate-500">
            {label ?? fieldKey}
          </span>
          {isConflict && (
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded"
              style={{ background: '#ede9fe', color: '#7c3aed' }}>Conflict</span>
          )}
          {hasBbox && onZoom && (
            <button
              onClick={() => onZoom(fieldKey)}
              className="text-slate-400 hover:text-blue-500 transition-colors"
              title="Jump to this field on the document"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </button>
          )}
        </div>
        <div className="flex items-center gap-1">
          {onMarkCorrect && onMarkWrong && (
            <div className="flex gap-0.5 mr-1">
              <button
                onClick={() => onMarkCorrect(fieldKey)}
                className={`w-5 h-5 rounded text-xs font-bold transition-colors ${feedbackState === 'correct' ? 'bg-green-500 text-white' : 'text-slate-300 hover:text-green-500 hover:bg-green-50'}`}
                title="Mark correct"
              >✓</button>
              <button
                onClick={() => onMarkWrong(fieldKey)}
                className={`w-5 h-5 rounded text-xs font-bold transition-colors ${feedbackState === 'wrong' ? 'bg-red-500 text-white' : 'text-slate-300 hover:text-red-500 hover:bg-red-50'}`}
                title="Mark wrong"
              >✗</button>
            </div>
          )}
          {isEdited && <span className="text-[10px] text-amber-600 font-bold">edited</span>}
          <span
            title={field.ai_reason}
            className={`text-xs font-semibold cursor-help ${pctColor}`}
          >{pct}%</span>
        </div>
      </div>

      {/* Smart input — edit mode */}
      {editing ? (
        <div className="flex gap-1.5 mt-1">
          {SELECT_FIELDS[fieldKey] ? (
            <select
              autoFocus
              className="flex-1 border border-blue-400 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
              value={draft}
              onChange={e => setDraft(e.target.value)}
            >
              {SELECT_FIELDS[fieldKey].map(v => (
                <option key={v} value={v}>{v || '— select —'}</option>
              ))}
            </select>
          ) : YESNO_FIELDS.has(fieldKey) ? (
            <select
              autoFocus
              className="flex-1 border border-blue-400 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
              value={draft}
              onChange={e => setDraft(e.target.value)}
            >
              <option value="Yes">Yes</option>
              <option value="No">No</option>
            </select>
          ) : DATE_FIELDS.has(fieldKey) ? (
            <input
              autoFocus
              type="date"
              className="flex-1 border border-blue-400 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') setEditing(false) }}
            />
          ) : (
            <input
              autoFocus
              type="text"
              className="flex-1 border border-blue-400 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') setEditing(false) }}
            />
          )}
          <button onClick={commitEdit} className="text-xs bg-blue-500 text-white px-2.5 py-1.5 rounded-lg hover:bg-blue-600 font-semibold">Save</button>
          <button onClick={() => setEditing(false)} className="text-xs text-slate-500 px-2 py-1.5 rounded-lg hover:bg-slate-100">✕</button>
        </div>
      ) : (
        <div
          className="text-sm text-slate-800 cursor-pointer hover:bg-white rounded-lg px-1 py-0.5 min-h-[1.5rem] group flex items-center gap-1 transition-colors"
          onClick={startEdit}
          title={field.ai_reason ? `AI reason: ${field.ai_reason}` : 'Click to edit'}
          style={isEdited ? { borderBottom: '1.5px solid #d97706', background: '#fffbeb' } : undefined}
        >
          <span className={displayValue ? 'font-medium' : 'text-slate-400 italic'}>
            {displayValue || 'empty'}
          </span>
          <span className="opacity-0 group-hover:opacity-60 text-slate-400 text-xs ml-auto">✏</span>
        </div>
      )}

      {/* Confidence bar */}
      <div className="mt-2 h-1.5 bg-slate-200 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: barColor }}
        />
      </div>

      {/* Conflict / low-conf reason */}
      {isConflict && (
        <p className="text-xs text-violet-700 mt-1.5 leading-snug font-medium">
          ⚡ Pass 1 &amp; Pass 2 disagreed — verify before approving.
        </p>
      )}
      {isLowConfidence && !isConflict && field.ai_reason && (
        <p className="text-xs text-amber-700 mt-1 leading-snug line-clamp-2">{field.ai_reason}</p>
      )}
    </div>
  )
}
