import { passStatusColors } from '../../utils/confidence'

interface Props {
  status: string
  notes: string | null
  escalationReason: string | null
}

export default function PassStatusBanner({ status, notes, escalationReason }: Props) {
  const { bg, text, label } = passStatusColors(status)
  const message = escalationReason || notes

  return (
    <div className={`${bg} ${text} rounded-xl px-4 py-3`}>
      <div className="flex items-center gap-3">
        <span className="text-2xl font-black tracking-wider">{label}</span>
        {message && <span className="text-sm opacity-90 leading-snug">{message}</span>}
      </div>
    </div>
  )
}
