const API_KEY = 'cdl-local-dev'
const headers = { 'x-api-key': API_KEY }

async function get(path: string) {
  const res = await fetch(`/api/v1${path}`, { headers })
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
}
