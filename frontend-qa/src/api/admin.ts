const API_KEY = import.meta.env.VITE_AI_ENGINE_API_KEY ?? 'cdl-local-dev'
const headers = { 'x-api-key': API_KEY }

async function get(path: string) {
  const res = await fetch(`/api/v1${path}`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

async function post(path: string, body?: unknown) {
  const res = await fetch(`/api/v1${path}`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export const adminApi = {
  overview: (days = 30) => get(`/admin/stats/overview?days=${days}`),
  fields:   (docType?: string) => get(`/admin/stats/fields${docType ? `?doc_type=${encodeURIComponent(docType)}` : ''}`),
  fieldDrilldown: (field: string) => get(`/admin/stats/fields/${encodeURIComponent(field)}`),
  agents:   (days = 30) => get(`/admin/stats/agents?days=${days}`),
  feed:     (limit = 100) => get(`/admin/stats/feed?limit=${limit}`),
  attorneys: () => get('/admin/stats/attorneys'),
  reviewQueue: () => get('/admin/review-queue'),
  approveTicket: (ticketId: string, reviewedBy = 'admin') =>
    post(`/admin/approve-ticket/${encodeURIComponent(ticketId)}`, { reviewed_by: reviewedBy }),
  rejectTicket: (ticketId: string, reason: string, reviewedBy = 'admin') =>
    post(`/admin/reject-ticket/${encodeURIComponent(ticketId)}`, { reason, reviewed_by: reviewedBy }),
}
