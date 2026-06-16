import { useState } from 'react'
import type { ProcessResponse } from './types/ticket'
import { uploadTicket } from './api/client'
import Header from './components/layout/Header'
import UploadZone from './components/upload/UploadZone'
import ReviewPanel from './components/review/ReviewPanel'
import RecentScansSidebar from './components/sidebar/RecentScansSidebar'
import AdminDashboard from './pages/AdminDashboard'
import './index.css'

type View = 'upload' | 'review' | 'admin'

interface ReviewState {
  data: ProcessResponse
  pages: string[]
  imageB64: string
}

export default function App() {
  const [view, setView] = useState<View>('upload')
  const [reviewState, setReviewState] = useState<ReviewState | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [sidebarRefresh, setSidebarRefresh] = useState(0)

  async function handleUpload(files: File[], driverName: string, promptVersion: string) {
    setUploading(true)
    setUploadError(null)
    try {
      const result = await uploadTicket(files, driverName || undefined, promptVersion)
      const allPages = await Promise.all(files.map(f => fileToBase64(f)))
      const imageB64 = allPages[0] ?? ''
      setReviewState({ data: result, pages: allPages, imageB64 })
      setView('review')
      setSidebarRefresh(n => n + 1)
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  function handleLoadFromSidebar(state: ReviewState) {
    setReviewState(state)
    setView('review')
  }

  function handleDone() {
    setView('upload')
    setReviewState(null)
    setSidebarRefresh(n => n + 1)
  }

  if (view === 'admin') {
    return (
      <div className="min-h-screen flex flex-col bg-gray-50">
        <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-4">
          <button onClick={handleDone} className="text-sm text-blue-600 hover:underline">← Back to Scanner</button>
        </div>
        <AdminDashboard />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Header onHome={handleDone} onAdmin={() => setView('admin')} />
      <div className="flex flex-1 overflow-hidden">
        <main className="flex-1 overflow-y-auto">
          {view === 'upload' && (
            <div>
              <UploadZone onUpload={handleUpload} loading={uploading} />
              {uploadError && (
                <div className="mx-auto max-w-xl mb-4 px-4">
                  <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
                    {uploadError}
                  </div>
                </div>
              )}
            </div>
          )}
          {view === 'review' && reviewState && (
            <ReviewPanel
              data={reviewState.data}
              pages={reviewState.pages}
              imageB64={reviewState.imageB64}
              onDone={handleDone}
            />
          )}
        </main>
        <RecentScansSidebar onLoadItem={handleLoadFromSidebar} refreshTick={sidebarRefresh} />
      </div>
    </div>
  )
}

async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      resolve(result.split(',')[1] ?? '')
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}
