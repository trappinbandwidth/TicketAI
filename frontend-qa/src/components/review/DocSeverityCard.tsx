import type { DocSeverityScore } from '../../types/ticket'
import { severityColors } from '../../utils/confidence'

interface Props {
  severity: DocSeverityScore
}

export default function DocSeverityCard({ severity }: Props) {
  const colors = severityColors(severity.severity)

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      {/* Header bar */}
      <div className={`${colors.bg} ${colors.text} px-4 py-2.5 flex items-center justify-between`}>
        <div className="flex items-center gap-2">
          <span className="font-bold text-sm tracking-wide">{severity.severity}</span>
          <span className="opacity-80 text-xs">— {severity.doc_type}</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-20 h-2 bg-black/20 rounded-full overflow-hidden">
            <div
              className="h-full bg-white/80 rounded-full transition-all"
              style={{ width: `${severity.severity_score}%` }}
            />
          </div>
          <span className="text-xs font-bold ml-1">{severity.severity_score}</span>
        </div>
      </div>

      <div className="p-4 space-y-3">
        {/* Key factors */}
        {severity.key_factors.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">Key Factors</p>
            <ul className="space-y-1">
              {severity.key_factors.map((f, i) => (
                <li key={i} className="flex items-start gap-1.5 text-sm text-gray-700">
                  <span className="text-gray-400 mt-0.5">•</span>
                  {f}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Action required */}
        <div className="bg-gray-50 rounded-lg px-3 py-2">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-0.5">Action Required</p>
          <p className="text-sm text-gray-800">{severity.action_required}</p>
          {severity.days_to_respond && (
            <p className="text-xs text-gray-500 mt-1">Response window: {severity.days_to_respond} days</p>
          )}
        </div>

        {/* Attorney rec */}
        {severity.attorney_recommended && (
          <div className="flex items-center gap-2 text-sm font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            <span>⚖️</span>
            <span>Attorney review recommended</span>
          </div>
        )}
      </div>
    </div>
  )
}
