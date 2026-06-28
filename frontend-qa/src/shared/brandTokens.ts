export const BRAND = {
  ink:      '#2D3142',
  inkDeep:  '#1A1E2E',
  teal:     '#2EC4A5',
  tealDark: '#1E9E85',
  tealTint: '#E8FAF6',
  offWhite: '#F8FAFC',
}

export const URGENCY_ORDER: Record<string, number> = { CRITICAL: 0, HIGH: 1, STANDARD: 2, LOW: 3 }
export const URGENCY_COLOR: Record<string, string> = {
  CRITICAL: '#DC2626',
  HIGH:     '#EA580C',
  STANDARD: '#2563EB',
  LOW:      '#6B7280',
}
export const URGENCY_BG: Record<string, string> = {
  CRITICAL: '#FEE2E2',
  HIGH:     '#FFEDD5',
  STANDARD: '#DBEAFE',
  LOW:      '#F3F4F6',
}

export const PASS_COLORS = { green: '#22c55e', yellow: '#eab308', red: '#ef4444', unknown: '#94a3b8' }
export const HEALTH_COLOR = (h: number) => h >= 0.9 ? '#22c55e' : h >= 0.75 ? '#eab308' : '#ef4444'
export const CONF_COLOR   = (c: number) => c >= 0.85 ? '#22c55e' : c >= 0.60 ? '#eab308' : '#ef4444'
export const DOC_COLORS   = ['#6366f1','#3b82f6','#06b6d4','#10b981','#f59e0b','#f97316','#ec4899']

export const PASS_BADGE: Record<string, string> = {
  green:  'bg-green-100 text-green-700',
  yellow: 'bg-yellow-100 text-yellow-700',
  red:    'bg-red-100 text-red-700',
}

export const REVIEWERS = ['Quest', 'Justin', 'Eniola'] as const
export type Reviewer = typeof REVIEWERS[number]

export function getStoredReviewer(): Reviewer {
  const stored = localStorage.getItem('rr_reviewer')
  return (REVIEWERS.includes(stored as Reviewer) ? stored : 'Quest') as Reviewer
}
