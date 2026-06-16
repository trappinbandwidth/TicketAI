/**
 * Real-time Firestore listener for the driver's ticket list.
 * Replaces the paginated REST query — updates arrive instantly
 * when the AI engine writes scan results back to Firestore.
 */
import { useState, useEffect } from 'react'
import { subscribeToTickets, type FirestoreTicket } from 'src/services/firestore'

interface UseTicketsRealtimeResult {
  tickets: FirestoreTicket[]
  loading: boolean
  error: string | null
}

export function useTicketsRealtime(driverId: string | null): UseTicketsRealtimeResult {
  const [tickets, setTickets] = useState<FirestoreTicket[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!driverId) {
      setTickets([])
      setLoading(false)
      return
    }

    setLoading(true)

    const unsubscribe = subscribeToTickets(
      driverId,
      (incoming) => {
        setTickets(incoming)
        setLoading(false)
      },
      (err) => {
        console.error('[useTicketsRealtime]', err)
        setError(err.message)
        setLoading(false)
      }
    )

    return unsubscribe
  }, [driverId])

  return { tickets, loading, error }
}
