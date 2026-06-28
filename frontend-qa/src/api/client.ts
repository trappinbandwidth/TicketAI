import type { ProcessResponse, QueueItem, QueueSummary } from '../types/ticket'

const API_KEY = import.meta.env.VITE_AI_ENGINE_API_KEY ?? 'cdl-local-dev'
const headers = { 'x-api-key': API_KEY }

export async function uploadTicket(
  files: File[],
  driverName?: string,
  promptVersion = 'v2',
): Promise<ProcessResponse> {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  if (driverName) form.append('driver_name', driverName)
  form.append('prompt_version', promptVersion)

  const res = await fetch('/api/v1/process', { method: 'POST', headers, body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Upload failed')
  }
  return res.json()
}

export async function listQueue(): Promise<QueueSummary[]> {
  const res = await fetch('/api/v1/queue', { headers })
  if (!res.ok) throw new Error('Failed to load queue')
  return res.json()
}

export async function getQueueItem(id: string): Promise<QueueItem> {
  const res = await fetch(`/api/v1/queue/${id}`, { headers })
  if (!res.ok) throw new Error('Failed to load queue item')
  return res.json()
}

export async function approveItem(id: string, editedFields: Record<string, string>) {
  const res = await fetch(`/api/v1/queue/${id}/approve`, {
    method: 'PUT',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ edited_fields: editedFields }),
  })
  if (!res.ok) throw new Error('Approve failed')
  return res.json()
}

export async function rejectItem(id: string, reason: string) {
  const res = await fetch(`/api/v1/queue/${id}/reject`, {
    method: 'PUT',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  })
  if (!res.ok) throw new Error('Reject failed')
  return res.json()
}

export async function getAuditTrail(id: string): Promise<any[]> {
  const res = await fetch(`/api/v1/queue/${id}/audit`, { headers })
  if (!res.ok) return []
  const data = await res.json()
  return Array.isArray(data) ? data : []
}
