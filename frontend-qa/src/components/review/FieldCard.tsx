import { useState } from 'react'
import { confidenceBadge } from '../../utils/confidence'
import type { FieldValue } from '../../types/ticket'

interface Props {
  fieldKey: string
  label?: string
  field: FieldValue
  isLowConfidence: boolean
  editedValue?: string
  onChange: (key: string, value: string) => void
  isActive?: boolean
  onZoom?: (key: string) => void
  // Feedback
  feedbackState?: 'correct' | 'wrong' | null
  onMarkCorrect?: (key: string) => void
  onMarkWrong?: (key: string) => void
}

export default function FieldCard({
  fieldKey, label, field, isLowConfidence, editedValue, onChange,
  isActive, onZoom, feedbackState, onMarkCorrect, onMarkWrong,
}: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const badge = confidenceBadge(field.confidence_score)
  const displayValue = editedValue !== undefined ? editedValue : field.value

  function startEdit() {
    setDraft(displayValue)
    setEditing(true)
  }

  function commitEdit() {
    onChange(fieldKey, draft)
    setEditing(false)
  }

  const isEdited = editedValue !== undefined && editedValue !== field.value
  const hasBbox = !!field.bbox

  let borderColor = 'border-gray-200'
  if (isActive) borderColor = 'border-blue-500'
  else if (isEdited) borderColor = 'border-blue-400'
  else if (feedbackState === 'wrong') borderColor = 'border-red-400'
  else if (feedbackState === 'correct') borderColor = 'border-green-400'
  else if (isLowConfidence) borderColor = 'border-red-300'

  return (
    <div
      className={`border-2 ${borderColor} rounded-lg p-3 bg-white transition-colors duration-200 ${isActive ? 'ring-2 ring-blue-200' : ''}`}
      id={`field-${fieldKey}`}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            {label ?? fieldKey}
          </span>
          {/* Zoom-to-field button — only shown if bbox is available */}
          {hasBbox && onZoom && (
            <button
              onClick={() => onZoom(fieldKey)}
              className="text-gray-400 hover:text-blue-500 transition-colors"
              title="Zoom to this field on the document"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
              </svg>
            </button>
          )}
        </div>

        <div className="flex items-center gap-1">
          {/* ✓ / ✗ feedback buttons */}
          {onMarkCorrect && onMarkWrong && (
            <div className="flex items-center gap-0.5 mr-1">
              <button
                onClick={() => onMarkCorrect(fieldKey)}
                className={`w-5 h-5 rounded text-xs font-bold transition-colors ${feedbackState === 'correct' ? 'bg-green-500 text-white' : 'text-gray-300 hover:text-green-500 hover:bg-green-50'}`}
                title="Mark as correct"
              >✓</button>
              <button
                onClick={() => onMarkWrong(fieldKey)}
                className={`w-5 h-5 rounded text-xs font-bold transition-colors ${feedbackState === 'wrong' ? 'bg-red-500 text-white' : 'text-gray-300 hover:text-red-500 hover:bg-red-50'}`}
                title="Mark as wrong"
              >✗</button>
            </div>
          )}
          {isEdited && <span className="text-xs text-blue-600 font-medium">edited</span>}
          <span
            title={field.ai_reason}
            className={`text-xs px-1.5 py-0.5 rounded border font-mono cursor-help ${badge.bg} ${badge.text} ${badge.border}`}
          >
            {badge.label}
          </span>
        </div>
      </div>

      {editing ? (
        <div className="flex gap-2 mt-1">
          <input
            autoFocus
            className="flex-1 border border-blue-400 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={draft}
            onChange={e => setDraft(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') setEditing(false) }}
          />
          <button onClick={commitEdit} className="text-xs bg-blue-500 text-white px-2 py-1 rounded hover:bg-blue-600">Save</button>
          <button onClick={() => setEditing(false)} className="text-xs text-gray-500 px-2 py-1 rounded hover:bg-gray-100">✕</button>
        </div>
      ) : (
        <div
          className="text-sm text-gray-800 cursor-pointer hover:bg-gray-50 rounded px-1 py-0.5 min-h-[1.5rem] group flex items-center gap-1"
          onClick={startEdit}
          title="Click to edit"
        >
          <span className={displayValue ? '' : 'text-gray-400 italic'}>{displayValue || 'empty'}</span>
          <span className="opacity-0 group-hover:opacity-100 text-gray-400 text-xs">✏️</span>
        </div>
      )}

      {field.ai_reason && (
        <p className="text-xs text-gray-400 mt-1 leading-snug line-clamp-2" title={field.ai_reason}>
          {field.ai_reason}
        </p>
      )}
    </div>
  )
}
