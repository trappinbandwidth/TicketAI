import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { adminApi } from '../api/admin'
import { BRAND, PASS_COLORS, DOC_COLORS } from '../shared/brandTokens'
import { KpiCard, SectionHeader, Spinner } from '../shared/SharedComponents'

export default function OverviewTab({ days }: { days: number }) {
  const [data, setData] = useState<any>(null)

  useEffect(() => {
    adminApi.overview(days).then(setData).catch(console.error)
  }, [days])

  if (!data) return <Spinner />
  if (data.total === 0) return (
    <div className="text-center py-16 text-gray-400">No scans in the last {days} days. Run some scans first.</div>
  )

  const pct = (n: number) => `${(n * 100).toFixed(1)}%`
  const docTypeData = Object.entries(data.doc_type_breakdown || {}).map(([name, value]) => ({ name, value }))

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <KpiCard label="Total Scans" value={data.total} sub={`Last ${days} days`} />
        <KpiCard label="Green Rate" value={pct(data.green_rate)} color={PASS_COLORS.green} />
        <KpiCard label="Yellow Rate" value={pct(data.yellow_rate)} color={PASS_COLORS.yellow} />
        <KpiCard label="Red Rate" value={pct(data.red_rate)} color={PASS_COLORS.red} />
        <KpiCard label="Attorney Match" value={pct(data.attorney_match_rate)} sub="of ticket scans" />
        <KpiCard label="Price Estimated" value={pct(data.price_estimate_rate)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-5">
          <SectionHeader title="Daily Scan Volume" subtitle="Stacked by pass status" />
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.daily_volume || []} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={d => d.slice(5)} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Bar dataKey="green"  stackId="a" fill={PASS_COLORS.green}  />
              <Bar dataKey="yellow" stackId="a" fill={PASS_COLORS.yellow} />
              <Bar dataKey="red"    stackId="a" fill={PASS_COLORS.red}    />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <SectionHeader title="Doc Types" />
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={docTypeData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80}
                label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`} labelLine={false}>
                {docTypeData.map((_, i) => <Cell key={i} fill={DOC_COLORS[i % DOC_COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-400 font-medium uppercase tracking-wide mb-1">Avg Confidence</p>
          <p className="text-2xl font-bold" style={{ color: BRAND.ink }}>{(data.avg_confidence * 100).toFixed(1)}%</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-400 font-medium uppercase tracking-wide mb-1">Dual Conflict Rate</p>
          <p className="text-2xl font-bold" style={{ color: data.dual_conflict_rate > 0.1 ? '#f59e0b' : BRAND.ink }}>
            {(data.dual_conflict_rate * 100).toFixed(1)}%
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-400 font-medium uppercase tracking-wide mb-1">Avg Price Low</p>
          <p className="text-2xl font-bold" style={{ color: BRAND.ink }}>${data.avg_price_low?.toFixed(0) ?? '—'}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-400 font-medium uppercase tracking-wide mb-1">Avg Price High</p>
          <p className="text-2xl font-bold" style={{ color: BRAND.ink }}>${data.avg_price_high?.toFixed(0) ?? '—'}</p>
        </div>
      </div>
    </div>
  )
}
