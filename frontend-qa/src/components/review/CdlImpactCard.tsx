import type { CdlPointImpact } from '../../types/ticket'

interface Props {
  impact: CdlPointImpact
}

export default function CdlImpactCard({ impact }: Props) {
  return (
    <div className="border border-orange-200 bg-orange-50 rounded-xl p-4">
      <h3 className="font-semibold text-orange-800 mb-3 flex items-center gap-2">
        <span>⚠️</span> CDL Point Impact
      </h3>
      <div className="grid grid-cols-2 gap-2 text-sm">
        {impact.cdl_points != null && (
          <div className="col-span-2 flex items-center gap-2">
            <span className="text-gray-600">Points:</span>
            <span className="font-bold text-orange-700 text-lg">{impact.cdl_points}</span>
          </div>
        )}
        <div>
          <span className="text-gray-500">Severity</span>
          <p className="font-medium text-gray-800">{impact.severity || '—'}</p>
        </div>
        <div>
          <span className="text-gray-500">CSA Category</span>
          <p className="font-medium text-gray-800">{impact.csa_category || '—'}</p>
        </div>
        <div>
          <span className="text-gray-500">Must Appear</span>
          <p className={`font-medium ${impact.must_appear_in_court ? 'text-red-600' : 'text-green-600'}`}>
            {impact.must_appear_in_court ? 'Yes' : 'No'}
          </p>
        </div>
        <div>
          <span className="text-gray-500">Attorney</span>
          <p className={`font-medium ${impact.attorney_recommended ? 'text-red-600' : 'text-gray-600'}`}>
            {impact.attorney_recommended ? 'Recommended' : 'Optional'}
          </p>
        </div>
      </div>
    </div>
  )
}
