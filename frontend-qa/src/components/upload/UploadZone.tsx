import { useState, useRef } from 'react'
import type { DragEvent } from 'react'

interface Props {
  onUpload: (files: File[], driverName: string, promptVersion: string) => void
  loading: boolean
}

export default function UploadZone({ onUpload, loading }: Props) {
  const [dragging, setDragging] = useState(false)
  const [driverName, setDriverName] = useState('')
  const [promptVersion, setPromptVersion] = useState('v2')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const fileRef = useRef<HTMLInputElement>(null)

  function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    const arr = Array.from(files)
    setSelectedFiles(arr)
  }

  function handleSubmit() {
    if (selectedFiles.length === 0 || loading) return
    onUpload(selectedFiles, driverName, promptVersion)
    setSelectedFiles([])
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  return (
    <div className="flex flex-col items-center gap-6 py-12 px-4">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-800">Rig Resolve — Document QA</h1>
        <p className="text-gray-500 mt-1">Upload any Rig Resolve document to scan, review, and approve</p>
      </div>

      <div className="w-full max-w-xl flex gap-3">
        <input
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Driver name (optional)"
          value={driverName}
          onChange={e => setDriverName(e.target.value)}
          disabled={loading}
        />
        <select
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          value={promptVersion}
          onChange={e => setPromptVersion(e.target.value)}
          disabled={loading}
        >
          <option value="v2">Prompt v2</option>
          <option value="v1">Prompt v1</option>
        </select>
      </div>

      <div
        className={`w-full max-w-xl border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-colors ${
          dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50'
        }`}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !loading && fileRef.current?.click()}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          multiple
          className="hidden"
          onChange={e => handleFiles(e.target.files)}
          disabled={loading}
        />
        {loading ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-gray-600 font-medium">Scanning with AI…</p>
          </div>
        ) : selectedFiles.length > 0 ? (
          <div className="flex flex-col items-center gap-2">
            <div className="text-4xl">📂</div>
            <p className="font-medium text-gray-700">{selectedFiles.length} file{selectedFiles.length > 1 ? 's' : ''} selected</p>
            <ul className="text-sm text-gray-500 text-left mt-1 space-y-0.5">
              {selectedFiles.map((f, i) => <li key={i}>• {f.name}</li>)}
            </ul>
            <p className="text-xs text-gray-400 mt-1">Click to change selection</p>
          </div>
        ) : (
          <>
            <div className="text-5xl mb-3">📄</div>
            <p className="text-gray-700 font-medium">Drop document here or click to browse</p>
            <p className="text-gray-400 text-sm mt-1">PDF, JPG, PNG · Multiple files for long tickets or CDL front &amp; back</p>
          </>
        )}
      </div>

      {selectedFiles.length > 0 && !loading && (
        <button
          onClick={handleSubmit}
          className="px-8 py-3 bg-blue-600 text-white rounded-xl font-semibold text-sm hover:bg-blue-700 transition-colors"
        >
          Scan {selectedFiles.length} File{selectedFiles.length > 1 ? 's' : ''}
        </button>
      )}
    </div>
  )
}
