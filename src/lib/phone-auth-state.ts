/**
 * Module-level holder for the Firebase ConfirmationResult.
 * ConfirmationResult is not JSON-serializable, so it lives here
 * rather than in localStorage or Jotai.
 */
import type { ConfirmationResult } from 'firebase/auth'

let _confirmation: ConfirmationResult | null = null

export function setConfirmation(c: ConfirmationResult): void {
  _confirmation = c
}

export function getConfirmation(): ConfirmationResult | null {
  return _confirmation
}

export function clearConfirmation(): void {
  _confirmation = null
}
