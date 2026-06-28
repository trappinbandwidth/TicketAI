interface Props {
  onHome: () => void
  onAdmin?: () => void
}

export default function Header({ onHome, onAdmin }: Props) {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shrink-0">
      <button onClick={onHome} className="flex items-center gap-3 hover:opacity-80">
        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
          CDL
        </div>
        <div className="text-left">
          <div className="font-bold text-gray-800 leading-none">Ticket Scanner QA</div>
          <div className="text-xs text-gray-400">Rig Resolve — AI Extraction Review</div>
        </div>
      </button>
      <div className="flex items-center gap-4">
        {onAdmin && (
          <button
            onClick={onAdmin}
            className="flex items-center gap-1.5 text-xs font-medium text-gray-600 hover:text-blue-600 bg-gray-100 hover:bg-blue-50 px-3 py-1.5 rounded-lg transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Dashboard
          </button>
        )}
        <a
          href="https://ai-ticket-engine-kajugdk3nq-uc.a.run.app/docs"
          target="_blank"
          rel="noreferrer"
          className="text-xs text-gray-400 hover:text-blue-500"
        >
          API Docs ↗
        </a>
      </div>
    </header>
  )
}
