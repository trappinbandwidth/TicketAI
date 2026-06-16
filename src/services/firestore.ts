/**
 * Firestore service — all ticket reads/writes for the driver app.
 *
 * Data lives at: drivers/{driverId}/tickets/{ticketId}
 */
import {
  collection,
  doc,
  addDoc,
  setDoc,
  getDoc,
  getDocs,
  query,
  orderBy,
  limit,
  onSnapshot,
  serverTimestamp,
  Timestamp,
  type Unsubscribe,
} from 'firebase/firestore'
import { db } from 'src/lib/firebase'

// ── Types ────────────────────────────────────────────────────────────────────

export type TicketStatus =
  | 'processing'   // AI engine is running
  | 'needs_review' // QA reviewer must approve
  | 'approved'     // Approved by reviewer, attorney assigned
  | 'rejected'     // Rejected
  | 'closed'       // Case resolved

export interface FirestoreTicket {
  id: string
  driver_id: string
  description: string
  image_urls: string[]         // Firebase Storage download URLs
  status: TicketStatus
  pass_status: 'green' | 'yellow' | 'red' | null
  ai_scan_id: string | null    // queue_id from the AI engine
  cached: boolean

  // AI-extracted fields (populated after processing)
  violation_category: string | null
  violation_description: string | null
  ticket_state: string | null
  ticket_county: string | null
  ticket_city: string | null
  court_date: string | null
  date_of_ticket: string | null
  citation_number: string | null
  drivers_license_type: string | null

  // Driver PII (extracted from ticket image)
  driver_first_name: string | null
  driver_last_name: string | null
  driver_dob: string | null
  driver_address: string | null
  cdl_license_number: string | null
  cdl_class: string | null

  // Matched attorney
  attorney_name: string | null
  attorney_phone: string | null
  attorney_email: string | null
  attorney_match_type: string | null

  // Price estimate
  price_display: string | null
  price_low: number | null
  price_high: number | null

  // Confidence + review
  referee_notes: string | null
  low_confidence_fields: string[]
  dual_conflicts: string[]

  created_at: Timestamp | null
  updated_at: Timestamp | null
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function ticketsRef(driverId: string) {
  return collection(db, 'drivers', driverId, 'tickets')
}

function ticketDocRef(driverId: string, ticketId: string) {
  return doc(db, 'drivers', driverId, 'tickets', ticketId)
}

function rowToTicket(id: string, data: Record<string, any>): FirestoreTicket {
  return {
    id,
    driver_id: data.driver_id ?? '',
    description: data.description ?? '',
    image_urls: data.image_urls ?? [],
    status: data.status ?? 'processing',
    pass_status: data.pass_status ?? null,
    ai_scan_id: data.ai_scan_id ?? null,
    cached: data.cached ?? false,
    violation_category: data.violation_category ?? null,
    violation_description: data.violation_description ?? null,
    ticket_state: data.ticket_state ?? null,
    ticket_county: data.ticket_county ?? null,
    ticket_city: data.ticket_city ?? null,
    court_date: data.court_date ?? null,
    date_of_ticket: data.date_of_ticket ?? null,
    citation_number: data.citation_number ?? null,
    drivers_license_type: data.drivers_license_type ?? null,
    driver_first_name: data.driver_first_name ?? null,
    driver_last_name: data.driver_last_name ?? null,
    driver_dob: data.driver_dob ?? null,
    driver_address: data.driver_address ?? null,
    cdl_license_number: data.cdl_license_number ?? null,
    cdl_class: data.cdl_class ?? null,
    attorney_name: data.attorney_name ?? null,
    attorney_phone: data.attorney_phone ?? null,
    attorney_email: data.attorney_email ?? null,
    attorney_match_type: data.attorney_match_type ?? null,
    price_display: data.price_display ?? null,
    price_low: data.price_low ?? null,
    price_high: data.price_high ?? null,
    referee_notes: data.referee_notes ?? null,
    low_confidence_fields: data.low_confidence_fields ?? [],
    dual_conflicts: data.dual_conflicts ?? [],
    created_at: data.created_at ?? null,
    updated_at: data.updated_at ?? null,
  }
}

// ── Write ────────────────────────────────────────────────────────────────────

/**
 * Create the initial ticket document before AI processing starts.
 * Returns the new Firestore document ID.
 */
export async function createTicketDoc(
  driverId: string,
  ticketId: string,
  payload: {
    description: string
    image_urls: string[]
  }
): Promise<void> {
  await setDoc(ticketDocRef(driverId, ticketId), {
    driver_id: driverId,
    description: payload.description,
    image_urls: payload.image_urls,
    status: 'processing',
    pass_status: null,
    ai_scan_id: null,
    cached: false,
    violation_category: null,
    violation_description: null,
    ticket_state: null,
    ticket_county: null,
    ticket_city: null,
    court_date: null,
    date_of_ticket: null,
    citation_number: null,
    drivers_license_type: null,
    driver_first_name: null,
    driver_last_name: null,
    driver_dob: null,
    driver_address: null,
    cdl_license_number: null,
    cdl_class: null,
    attorney_name: null,
    attorney_phone: null,
    attorney_email: null,
    attorney_match_type: null,
    price_display: null,
    price_low: null,
    price_high: null,
    referee_notes: null,
    low_confidence_fields: [],
    dual_conflicts: [],
    created_at: serverTimestamp(),
    updated_at: serverTimestamp(),
  })
}

// ── Read ─────────────────────────────────────────────────────────────────────

export async function getTicket(driverId: string, ticketId: string): Promise<FirestoreTicket | null> {
  const snap = await getDoc(ticketDocRef(driverId, ticketId))
  if (!snap.exists()) return null
  return rowToTicket(snap.id, snap.data())
}

export async function listTickets(driverId: string, maxResults = 50): Promise<FirestoreTicket[]> {
  const q = query(ticketsRef(driverId), orderBy('created_at', 'desc'), limit(maxResults))
  const snap = await getDocs(q)
  return snap.docs.map((d) => rowToTicket(d.id, d.data()))
}

// ── Real-time ─────────────────────────────────────────────────────────────────

/**
 * Subscribe to the driver's full ticket list in real-time.
 * Returns an unsubscribe function — call it in a useEffect cleanup.
 */
export function subscribeToTickets(
  driverId: string,
  onUpdate: (tickets: FirestoreTicket[]) => void,
  onError?: (err: Error) => void
): Unsubscribe {
  const q = query(ticketsRef(driverId), orderBy('created_at', 'desc'), limit(100))
  return onSnapshot(
    q,
    (snap) => onUpdate(snap.docs.map((d) => rowToTicket(d.id, d.data()))),
    onError
  )
}

/**
 * Subscribe to a single ticket document — useful for the processing status screen.
 */
export function subscribeToTicket(
  driverId: string,
  ticketId: string,
  onUpdate: (ticket: FirestoreTicket | null) => void,
  onError?: (err: Error) => void
): Unsubscribe {
  return onSnapshot(
    ticketDocRef(driverId, ticketId),
    (snap) => onUpdate(snap.exists() ? rowToTicket(snap.id, snap.data()) : null),
    onError
  )
}
