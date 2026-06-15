import { useState } from 'react'

interface Props {
  onApprove: () => void
  onReject: (reason: string) => void
  loading: boolean
  editCount: number
}

export default function ActionBar({ onApprove, onReject, loading, editCount }: Props) {
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')

  function submitReject() {
    onReject(reason)
    setRejecting(false)
    setReason('')
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      {rejecting ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm font-medium text-gray-700">Reason for rejection (optional)</p>
          <textarea
            autoFocus
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-red-400"
            rows={2}
            placeholder="e.g. Poor scan quality, wrong document type…"
            value={reason}
            onChange={e => setReason(e.target.value)}
          />
          <div className="flex gap-2">
            <button
              onClick={submitReject}
              disabled={loading}
              className="flex-1 bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded-lg disabled:opacity-50"
            >
              Confirm Reject
            </button>
            <button
              onClick={() => { setRejecting(false); setReason('') }}
              className="px-4 py-2 text-gray-500 hover:bg-gray-100 rounded-lg text-sm"
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
            className="flex-1 bg-green-500 hover:bg-green-600 text-white font-semibold py-3 px-4 rounded-lg disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? (
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <span>✓</span>
                Approve{editCount > 0 ? ` (${editCount} edit${editCount > 1 ? 's' : ''})` : ''}
              </>
            )}
          </button>
          <button
            onClick={() => setRejecting(true)}
            disabled={loading}
            className="flex-1 bg-red-50 hover:bg-red-100 text-red-600 font-semibold py-3 px-4 rounded-lg border border-red-200 disabled:opacity-50"
          >
            ✕ Reject
          </button>
        </div>
      )}
    </div>
  )
}
