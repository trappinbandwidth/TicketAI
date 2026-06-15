export function confidenceBadge(score: number): {
  label: string; bg: string; text: string; border: string
} {
  if (score >= 0.85) return { label: `${Math.round(score * 100)}%`, bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-300' }
  if (score >= 0.60) return { label: `${Math.round(score * 100)}%`, bg: 'bg-yellow-100', text: 'text-yellow-800', border: 'border-yellow-300' }
  return { label: `${Math.round(score * 100)}%`, bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-300' }
}

export function passStatusColors(status: string): { bg: string; text: string; label: string } {
  switch (status) {
    case 'green':  return { bg: 'bg-green-500',  text: 'text-white',        label: 'PASS' }
    case 'yellow': return { bg: 'bg-yellow-400', text: 'text-yellow-900',   label: 'REVIEW' }
    case 'red':    return { bg: 'bg-red-500',    text: 'text-white',        label: 'ESCALATE' }
    default:       return { bg: 'bg-gray-400',   text: 'text-white',        label: status.toUpperCase() }
  }
}

export function statusBadge(status: string): { bg: string; text: string } {
  switch (status) {
    case 'approved': return { bg: 'bg-green-100', text: 'text-green-700' }
    case 'rejected': return { bg: 'bg-red-100',   text: 'text-red-700' }
    default:         return { bg: 'bg-yellow-100', text: 'text-yellow-700' }
  }
}

export function severityColors(severity: string): { bg: string; text: string; border: string } {
  switch (severity) {
    case 'CRITICAL': return { bg: 'bg-red-600',    text: 'text-white',       border: 'border-red-700' }
    case 'HIGH':     return { bg: 'bg-orange-500', text: 'text-white',       border: 'border-orange-600' }
    case 'MEDIUM':   return { bg: 'bg-yellow-400', text: 'text-yellow-900',  border: 'border-yellow-500' }
    default:         return { bg: 'bg-green-100',  text: 'text-green-800',   border: 'border-green-300' }
  }
}
