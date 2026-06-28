import { useState } from 'react'
import { B, STAFF, useStaff } from '../shared/CpComponents'
import CpDashboardTab from './CpDashboardTab'
import CpDriversTab from './CpDriversTab'
import CpAttorneysTab from './CpAttorneysTab'
import CpCarriersTab from './CpCarriersTab'
import CpCasesTab from './CpCasesTab'

const TABS = ['Dashboard', 'Drivers', 'Attorneys', 'Carriers', 'Cases'] as const
type CPTab = typeof TABS[number]

export default function ControlPanel() {
  const [tab, setTab] = useState<CPTab>('Dashboard')
  const { staff, setStaff } = useStaff()

  return (
    <div className="min-h-screen" style={{ background: B.offWhite }}>
      {/* Header */}
      <div className="px-6 py-4 flex items-center justify-between shrink-0" style={{ background: B.inkDeep }}>
        <div className="flex items-center gap-4">
          <a href="#/" className="text-xs font-medium transition-colors hover:opacity-80" style={{ color: '#475569' }}>
            ← Scanner Admin
          </a>
          <div>
            <div style={{ fontFamily: "'Inter', sans-serif", fontSize: 20, fontWeight: 900, letterSpacing: -0.5, color: '#F1F5F9' }}>
              rig<span style={{ color: B.teal }}>(</span>resolve
              <span style={{ color: '#475569', fontSize: 12, fontWeight: 500, marginLeft: 12 }}>Control Panel</span>
            </div>
            <p className="text-xs mt-0.5" style={{ color: '#475569' }}>Business operations — drivers · attorneys · carriers · cases</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: '#475569' }}>Staff:</span>
          <div className="flex gap-1">
            {STAFF.map(s => (
              <button key={s} onClick={() => setStaff(s)}
                className="px-2.5 py-1 rounded-lg text-xs font-semibold transition-all"
                style={staff === s
                  ? { background: B.teal, color: B.inkDeep }
                  : { background: 'rgba(255,255,255,0.08)', color: '#94A3B8' }}>
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200 px-6 flex gap-1">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className="px-4 py-3 text-sm font-medium border-b-2 transition-colors"
            style={tab === t
              ? { borderColor: B.teal, color: B.teal }
              : { borderColor: 'transparent', color: '#6B7280' }}>
            {t}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="p-6">
        {tab === 'Dashboard' && <CpDashboardTab />}
        {tab === 'Drivers'   && <CpDriversTab />}
        {tab === 'Attorneys' && <CpAttorneysTab />}
        {tab === 'Carriers'  && <CpCarriersTab />}
        {tab === 'Cases'     && <CpCasesTab />}
      </div>
    </div>
  )
}
