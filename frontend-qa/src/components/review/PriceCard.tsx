import type { PriceEstimate } from '../../types/ticket'

interface Props {
  estimate: PriceEstimate
}

export default function PriceCard({ estimate }: Props) {
  const isUnavailable = estimate.data_source === 'unavailable' || estimate.driver_price_base === 0

  return (
    <div className={`rounded-2xl p-5 ${estimate.high_risk ? 'bg-orange-500' : 'bg-emerald-600'} text-white shadow-lg`}>
      {/* Header row */}
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-semibold uppercase tracking-widest opacity-80">
          Estimated Driver Price
        </span>
        <div className="flex items-center gap-2">
          {estimate.high_risk && (
            <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full font-semibold">
              ⚠ High Risk
            </span>
          )}
          {estimate.data_source === 'fallback' && (
            <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full">
              State avg
            </span>
          )}
        </div>
      </div>

      {/* Big price range */}
      {isUnavailable ? (
        <p className="text-3xl font-bold tracking-tight opacity-60 mt-1">Unavailable</p>
      ) : (
        <p className="text-4xl font-extrabold tracking-tight mt-1">
          {estimate.display}
        </p>
      )}

      {/* Sub-line: breakdown */}
      {!isUnavailable && (
        <p className="text-sm opacity-75 mt-1">
          Atty avg <strong>${estimate.avg_attny_price.toLocaleString()}</strong>
          {' '}+ CDL fee <strong>${estimate.cdl_fee}</strong>
          {' '}= base <strong>${estimate.driver_price_base.toLocaleString()}</strong>
          {' '}(±15–20%)
        </p>
      )}

      {/* Stats row */}
      {!isUnavailable && (
        <div className="flex items-center gap-4 mt-3 pt-3 border-t border-white/20 text-sm">
          <div className="flex flex-col">
            <span className="text-xs opacity-60 uppercase tracking-wide">Win Rate</span>
            <span className="font-bold text-lg">
              {estimate.win_rate_pct > 0 ? `${estimate.win_rate_pct}%` : '—'}
            </span>
          </div>
          <div className="w-px h-8 bg-white/20" />
          <div className="flex flex-col">
            <span className="text-xs opacity-60 uppercase tracking-wide">Sample Size</span>
            <span className="font-bold text-lg">
              {estimate.sample_size > 0 ? `${estimate.sample_size.toLocaleString()} tickets` : '—'}
            </span>
          </div>
          <div className="w-px h-8 bg-white/20" />
          <div className="flex flex-col">
            <span className="text-xs opacity-60 uppercase tracking-wide">Data Source</span>
            <span className="font-bold capitalize">{estimate.data_source}</span>
          </div>
        </div>
      )}

      {/* Fallback note */}
      {estimate.note && (
        <p className="text-xs opacity-60 mt-2 italic">{estimate.note}</p>
      )}
    </div>
  )
}
