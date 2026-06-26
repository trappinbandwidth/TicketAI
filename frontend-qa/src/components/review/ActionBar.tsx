import { useState, useEffect } from 'react'

interface Props {
  onApprove: () => void
  onReject: (reason: string) => void
  loading: boolean
  editCount: number
}

const TEAL = '#2EC4A5'
const INK  = '#1A1E2E'

export default function ActionBar({ onApprove, onReject, loading, editCount }: Props) {
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [reviewer, setReviewer] = useState('')

  useEffect(() => {
    setReviewer(localStorage.getItem('rr_reviewer') || '')
    const sync = () => setReviewer(localStorage.getItem('rr_reviewer') || '')
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [])

  function submitReject() {
    onReject(reason)
    setRejecting(false)
    setReason('')
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
      {reviewer && (
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>Reviewing as:</span>
          <span className="font-bold px-2 py-0.5 rounded-full text-xs"
            style={{ background: '#E8FAF6', color: TEAL, border: `1.5px solid ${TEAL}` }}>
            {reviewer}
          </span>
          {editCount > 0 && (
            <span className="ml-auto text-amber-600 font-semibold">
              {editCount} edit{editCount > 1 ? 's' : ''} pending
            </span>
          )}
        </div>
      )}

      {rejecting ? (
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium text-slate-700">Reason for rejection <span className="text-slate-400 font-normal">(optional)</span></p>
          <input
            autoFocus
            type="text"
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            placeholder="e.g. Poor scan quality, wrong document type…"
            value={reason}
            onChange={e => setReason(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') submitReject(); if (e.key === 'Escape') { setRejecting(false); setReason('') } }}
          />
          <div className="flex gap-2">
            <button
              onClick={submitReject}
              disabled={loading}
              className="flex-1 bg-red-600 hover:bg-red-700 text-white font-semibold py-2 px-4 rounded-lg disabled:opacity-50 transition-colors"
            >
              Confirm Reject
            </button>
            <button
              onClick={() => { setRejecting(false); setReason('') }}
              className="px-4 py-2 text-slate-500 hover:bg-slate-100 rounded-lg text-sm transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex gap-3">
          <button
            onClick={onApprove}
            disabled={loading}
            className="flex-1 font-bold py-3 px-4 rounded-xl disabled:opacity-50 flex items-center justify-center gap-2 transition-all"
            style={{ background: TEAL, color: INK }}
          >
            {loading ? (
              <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <span>✓</span>
                Approve {editCount > 0 ? `(${editCount} edit${editCount > 1 ? 's' : ''})` : '& Save'}
              </>
            )}
          </button>
          <button
            onClick={() => setRejecting(true)}
            disabled={loading}
            className="flex-1 font-semibold py-3 px-4 rounded-xl border border-red-200 disabled:opacity-50 transition-colors"
            style={{ background: '#FEF2F2', color: '#DC2626' }}
          >
            ✕ Reject
          </button>
        </div>
      )}
    </div>
  )
}
