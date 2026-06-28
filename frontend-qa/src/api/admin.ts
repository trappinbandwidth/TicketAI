const API_KEY = import.meta.env.VITE_AI_ENGINE_API_KEY ?? 'cdl-local-dev'
const headers = { 'x-api-key': API_KEY }

// Detect Firebase Hosting and call Cloud Run directly to avoid 60s proxy timeout
function baseUrl() {
  const h = window.location.hostname
  if (h.endsWith('.web.app') || h.endsWith('.firebaseapp.com')) {
    return 'https://ai-ticket-engine-kajugdk3nq-uc.a.run.app'
  }
  const port = parseInt(window.location.port, 10)
  if (!port || port === 80 || port === 443) return window.location.origin
  return `${window.location.protocol}//${window.location.hostname}:8000`
}

async function get(path: string) {
  const res = await fetch(`${baseUrl()}/api/v1${path}`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

async function post(path: string, body?: unknown) {
  const res = await fetch(`${baseUrl()}/api/v1${path}`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

async function put(path: string, body?: unknown) {
  const res = await fetch(`${baseUrl()}/api/v1${path}`, {
    method: 'PUT',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

async function del(path: string) {
  const res = await fetch(`${baseUrl()}/api/v1${path}`, { method: 'DELETE', headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}


export const adminApi = {
  // Analytics
  overview:       (days = 30) => get(`/admin/stats/overview?days=${days}`),
  fields:         (docType?: string) => get(`/admin/stats/fields${docType ? `?doc_type=${encodeURIComponent(docType)}` : ''}`),
  fieldDrilldown: (field: string) => get(`/admin/stats/fields/${encodeURIComponent(field)}`),
  agents:         (days = 30) => get(`/admin/stats/agents?days=${days}`),
  feed:           (limit = 100) => get(`/admin/stats/feed?limit=${limit}`),
  attorneys:      () => get('/admin/stats/attorneys'),

  // Review queue
  reviewQueue:  () => get('/admin/review-queue'),
  approveTicket: (ticketId: string, reviewedBy = 'admin') =>
    post(`/admin/approve-ticket/${encodeURIComponent(ticketId)}?reviewer_id=${encodeURIComponent(reviewedBy)}`),
  rejectTicket: (ticketId: string, reason: string) =>
    post(`/admin/reject-ticket/${encodeURIComponent(ticketId)}?reason=${encodeURIComponent(reason)}`),

  // Cases
  attorneysList:    () => get('/admin/attorneys/list'),
  availableTickets: () => get('/admin/cases/available'),
  listCases:        (status?: string) => get(`/admin/cases${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  createCase:       (body: { ticket_id: string; attorney_id: string; assigned_by: string; contact_method?: string; note?: string }) =>
    post('/admin/cases', body),
  getCase:          (caseId: string) => get(`/admin/cases/${encodeURIComponent(caseId)}`),
  logActivity:      (caseId: string, body: { type: string; note: string; new_status?: string; created_by: string; created_by_name?: string }) =>
    post(`/admin/cases/${encodeURIComponent(caseId)}/activity`, body),
  recordOutcome:    (ticketId: string, body: { outcome: string; outcome_notes?: string; final_charge?: string; attorney_id?: string; attorney_name?: string }) =>
    post(`/operations/record-outcome/${encodeURIComponent(ticketId)}`, body),

  // Operations
  courtDeadlines:  (sendReminders = false) =>
    post(`/operations/court-deadlines?send_driver_reminders=${sendReminders}`),
  paymentAlerts:   () => get('/operations/payment-alerts'),
  caseStatus:      (state?: string, urgency?: string) => {
    const params = new URLSearchParams()
    if (state) params.set('state', state)
    if (urgency) params.set('urgency', urgency)
    const qs = params.toString()
    return get(`/operations/case-status${qs ? `?${qs}` : ''}`)
  },
}

// ── Attorney Network API ───────────────────────────────────────────────────────
export const attorneyNetworkApi = {
  list:     (params?: { state?: string; status?: string; assigned_to?: string; cdl_specialist?: boolean; limit?: number }) => {
    const qs = new URLSearchParams()
    if (params?.state)          qs.set('state', params.state)
    if (params?.status)         qs.set('status', params.status)
    if (params?.assigned_to)    qs.set('assigned_to', params.assigned_to)
    if (params?.cdl_specialist != null) qs.set('cdl_specialist', String(params.cdl_specialist))
    if (params?.limit)          qs.set('limit', String(params.limit))
    return get(`/attorneys?${qs.toString()}`)
  },
  get:          (id: string)   => get(`/attorneys/${encodeURIComponent(id)}`),
  pipeline:     ()             => get('/attorneys/pipeline'),
  coverage:     ()             => get('/attorneys/states/coverage'),
  match:        (state: string, county?: string) => {
    const qs = new URLSearchParams({ state })
    if (county) qs.set('county', county)
    return get(`/attorneys/match?${qs}`)
  },
  updateOutreach: async (id: string, body: {
    status?: string; assigned_to?: string; outreach_notes?: string; follow_up_at?: string
  }) => {
    const res = await fetch(`${baseUrl()}/api/v1/attorneys/${encodeURIComponent(id)}/outreach`, {
      method: 'PATCH',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },
  updatePricing: async (id: string, body: {
    pricing_flat_rate?: string; pricing_volume?: string;
    pricing_per_type?: Record<string, string>;
    states_covered?: string[]; counties_covered?: string[];
  }) => {
    const res = await fetch(`${baseUrl()}/api/v1/attorneys/${encodeURIComponent(id)}/pricing`, {
      method: 'PATCH',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },
}

// ── Control Panel API ──────────────────────────────────────────────────────────
export const controlApi = {
  // KPI
  kpi: () => get('/admin/kpi'),

  // Drivers
  listDrivers:   () => get('/admin/drivers'),
  getDriver:     (id: string) => get(`/admin/drivers/${encodeURIComponent(id)}`),
  createDriver:  (body: Record<string, unknown>) => post('/admin/drivers', body),
  updateDriver:  (id: string, body: Record<string, unknown>) => put(`/admin/drivers/${encodeURIComponent(id)}`, body),

  // Attorneys management
  listAttorneys:   () => get('/admin/attorneys-mgmt'),
  createAttorney:  (body: Record<string, unknown>) => post('/admin/attorneys-mgmt', body),
  updateAttorney:  (id: string, body: Record<string, unknown>) => put(`/admin/attorneys-mgmt/${encodeURIComponent(id)}`, body),
  removeAttorney:  (id: string) => del(`/admin/attorneys-mgmt/${encodeURIComponent(id)}`),
  approveAttorney: (id: string) => put(`/admin/attorneys-mgmt/${encodeURIComponent(id)}`, { status: 'active' }),
  denyAttorney:    (id: string) => put(`/admin/attorneys-mgmt/${encodeURIComponent(id)}`, { status: 'inactive' }),

  // Carriers management
  listCarriers:   () => get('/admin/carriers'),
  createCarrier:  (body: Record<string, unknown>) => post('/admin/carriers', body),
  updateCarrier:  (id: string, body: Record<string, unknown>) => put(`/admin/carriers/${encodeURIComponent(id)}`, body),
  removeCarrier:  (id: string) => del(`/admin/carriers/${encodeURIComponent(id)}`),
  approveCarrier: (id: string) => put(`/admin/carriers/${encodeURIComponent(id)}`, { status: 'active' }),
  denyCarrier:    (id: string) => put(`/admin/carriers/${encodeURIComponent(id)}`, { status: 'inactive' }),

  // Bids
  requestBids:  (caseId: string, body: Record<string, unknown>) => post(`/admin/cases/${encodeURIComponent(caseId)}/request-bids`, body),
  listBids:     (caseId: string) => get(`/admin/cases/${encodeURIComponent(caseId)}/bids`),
  submitBid:    (caseId: string, body: Record<string, unknown>) => post(`/admin/cases/${encodeURIComponent(caseId)}/bids`, body),
  updateBid:    (caseId: string, bidId: string, body: Record<string, unknown>) => put(`/admin/cases/${encodeURIComponent(caseId)}/bids/${encodeURIComponent(bidId)}`, body),
  deleteBid:    (caseId: string, bidId: string) => del(`/admin/cases/${encodeURIComponent(caseId)}/bids/${encodeURIComponent(bidId)}`),
  selectBid:    (caseId: string, bidId: string, body: Record<string, unknown>) => post(`/admin/cases/${encodeURIComponent(caseId)}/bids/${encodeURIComponent(bidId)}/select`, body),
  searchBids:   (params: { state?: string; county?: string; violation?: string }) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([,v]) => v) as [string,string][]).toString()
    return get(`/admin/bids/search${qs ? `?${qs}` : ''}`)
  },

  // Cases (via existing cases routes + new financial routes)
  listCases:       (status?: string) => get(`/admin/cases${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  getCase:         (id: string) => get(`/admin/cases/${encodeURIComponent(id)}`),
  createCase:      (body: Record<string, unknown>) => post('/admin/cases', body),
  logActivity:     (id: string, body: Record<string, unknown>) => post(`/admin/cases/${encodeURIComponent(id)}/activity`, body),
  updateFees:      (id: string, body: Record<string, unknown>) => put(`/admin/cases/${encodeURIComponent(id)}/fees`, body),
  recordPayout:    (id: string, body: Record<string, unknown>) => post(`/admin/cases/${encodeURIComponent(id)}/payout`, body),
  recordOutcome:   (ticketId: string, body: Record<string, unknown>) => post(`/operations/record-outcome/${encodeURIComponent(ticketId)}`, body),
  availableTickets: () => get('/admin/cases/available'),
  attorneysList:    () => get('/admin/attorneys/list'),
}
