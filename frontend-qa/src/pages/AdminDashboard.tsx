import { useState } from 'react'
import { BRAND, REVIEWERS, getStoredReviewer } from '../shared/brandTokens'
import type { Reviewer } from '../shared/brandTokens'
import ScannerTab from './ScannerTab'
import ReviewQueueTab from './ReviewQueueTab'
import OverviewTab from './OverviewTab'
import FieldsTab from './FieldsTab'
import AgentsTab from './AgentsTab'
import ScanFeedTab from './ScanFeedTab'
import AttorneysStatsTab from './AttorneysStatsTab'
import CasesTab from './CasesTab'
import OperationsTab from './OperationsTab'
import AttorneyNetworkTab from './AttorneyNetworkTab'

const TABS = ['Scanner', 'Review Queue', 'Cases', 'Operations', 'Overview', 'Fields', 'Agents', 'Scan Feed', 'Attorneys', 'Network'] as const
type Tab = typeof TABS[number]

const NAV_ICONS: Record<Tab, React.ReactNode> = {
  'Scanner': (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 7V5a1 1 0 011-1h2M4 17v2a1 1 0 001 1h2m10-16h2a1 1 0 011 1v2m0 10v2a1 1 0 01-1 1h-2M9 12h6M9 9h6M9 15h4" />
    </svg>
  ),
  'Review Queue': (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
    </svg>
  ),
  'Cases': (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M20 7H4a2 2 0 00-2 2v10a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2zM16 3H8a2 2 0 00-2 2v2h12V5a2 2 0 00-2-2z" />
    </svg>
  ),
  'Operations': (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
  ),
  'Overview': (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  ),
  'Fields': (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 10h18M3 14h18M10 4v16M6 4h12a2 2 0 012 2v12a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2z" />
    </svg>
  ),
  'Agents': (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
    </svg>
  ),
  'Scan Feed': (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 6h16M4 10h16M4 14h10M4 18h6" />
    </svg>
  ),
  'Attorneys': (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 6l9-3 9 3M3 6v12l9 3 9-3V6M12 3v18" />
    </svg>
  ),
  'Network': (
    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  ),
}

export default function AdminDashboard() {
  const [tab, setTab] = useState<Tab>('Review Queue')
  const [days, setDays] = useState(30)
  const [queueCount, setQueueCount] = useState<number | null>(null)
  const [reviewer, setReviewer] = useState<Reviewer>(getStoredReviewer)

  function handleReviewerChange(r: Reviewer) {
    setReviewer(r)
    localStorage.setItem('rr_reviewer', r)
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: BRAND.offWhite }}>

      {/* Top nav */}
      <div className="shrink-0 flex items-center justify-between px-5 py-3"
        style={{ background: BRAND.ink, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>

        <div style={{ fontFamily: "'Inter', sans-serif", fontSize: 18, fontWeight: 900, letterSpacing: -0.5, color: '#F1F5F9' }}>
          rig<span style={{ color: BRAND.teal }}>(</span>resolve
          <span style={{ color: '#475569', fontSize: 11, fontWeight: 500, marginLeft: 10 }}>Control Panel</span>
        </div>

        <div className="flex items-center gap-5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium" style={{ color: '#64748B' }}>Reviewer</span>
            <div className="flex gap-1">
              {REVIEWERS.map(r => (
                <button key={r} onClick={() => handleReviewerChange(r)}
                  className="px-2.5 py-1 rounded-lg text-xs font-semibold transition-all"
                  style={reviewer === r
                    ? { background: BRAND.teal, color: BRAND.inkDeep }
                    : { background: 'rgba(255,255,255,0.08)', color: '#94A3B8' }}>
                  {r}
                </button>
              ))}
            </div>
          </div>

          <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.1)' }} />

          <div className="flex items-center gap-1.5">
            <span className="text-xs font-medium" style={{ color: '#64748B' }}>Last</span>
            {[7, 30, 90].map(d => (
              <button key={d} onClick={() => setDays(d)}
                className="px-2.5 py-1 rounded-lg text-xs font-semibold transition-all"
                style={days === d
                  ? { background: BRAND.teal, color: BRAND.inkDeep }
                  : { background: 'rgba(255,255,255,0.08)', color: '#94A3B8' }}>
                {d}d
              </button>
            ))}
          </div>

          <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.1)' }} />

          <a href="/scanner.html" target="_blank" rel="noreferrer" title="Open scanner in new tab"
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all"
            style={{ background: 'rgba(255,255,255,0.06)', color: '#94A3B8' }}>
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            Scanner
          </a>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">

        {/* Sidebar */}
        <nav className="w-52 shrink-0 flex flex-col overflow-y-auto py-3"
          style={{ background: BRAND.inkDeep, borderRight: '1px solid rgba(255,255,255,0.05)' }}>

          <div className="px-4 mb-3">
            <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: '#334155' }}>Navigation</span>
          </div>

          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)}
              className="flex items-center gap-3 px-4 py-2.5 text-sm font-medium text-left w-full transition-all"
              style={tab === t
                ? { background: 'rgba(46,196,165,0.1)', color: BRAND.teal, borderLeft: `3px solid ${BRAND.teal}`, paddingLeft: '13px' }
                : { color: '#64748B', borderLeft: '3px solid transparent', paddingLeft: '13px' }}>
              {NAV_ICONS[t]}
              <span className="flex-1">{t}</span>
              {t === 'Review Queue' && queueCount !== null && queueCount > 0 && (
                <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full leading-none">{queueCount}</span>
              )}
            </button>
          ))}
        </nav>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          {tab === 'Scanner'      && <ScannerTab />}
          {tab === 'Review Queue' && <ReviewQueueTab onCountChange={setQueueCount} reviewer={reviewer} />}
          {tab === 'Cases'        && <CasesTab reviewer={reviewer} />}
          {tab === 'Operations'   && <OperationsTab />}
          {tab === 'Overview'     && <OverviewTab days={days} />}
          {tab === 'Fields'       && <FieldsTab days={days} />}
          {tab === 'Agents'       && <AgentsTab days={days} />}
          {tab === 'Scan Feed'    && <ScanFeedTab />}
          {tab === 'Attorneys'    && <AttorneysStatsTab />}
          {tab === 'Network'      && <AttorneyNetworkTab />}
        </main>

      </div>
    </div>
  )
}
