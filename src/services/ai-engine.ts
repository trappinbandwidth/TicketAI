/**
 * AI Ticket Engine client.
 * Sends ticket images to the FastAPI backend for extraction.
 */

const AI_ENGINE_URL = import.meta.env.VITE_AI_ENGINE_URL ?? 'http://localhost:8000'
const AI_ENGINE_API_KEY = import.meta.env.VITE_AI_ENGINE_API_KEY ?? 'cdl-local-dev'

export interface AiEngineResponse {
  success: boolean
  queue_id: string
  pass_status: string
  cached: boolean
  filename: string
  pages_processed: number
  result: Record<string, any>
  attorney_matches: any[]
  price_estimate: any | null
  referee_notes: string | null
  low_confidence_fields: string[]
  dual_conflicts: string[]
  escalation_reason: string | null
}

/**
 * Submit ticket files to the AI engine for extraction.
 * driver_id and ticket_id are passed so the engine can write
 * results back to Firestore directly.
 */
export async function submitToAiEngine(
  files: File[],
  driverName: string,
  driverId: string,
  ticketId: string,
  promptVersion = 'v2'
): Promise<AiEngineResponse> {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f))
  formData.append('driver_name', driverName)
  formData.append('driver_id', driverId)
  formData.append('ticket_id', ticketId)
  formData.append('prompt_version', promptVersion)

  const res = await fetch(`${AI_ENGINE_URL}/process`, {
    method: 'POST',
    headers: { 'X-API-Key': AI_ENGINE_API_KEY },
    body: formData,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `AI engine error: ${res.status}`)
  }

  return res.json()
}
