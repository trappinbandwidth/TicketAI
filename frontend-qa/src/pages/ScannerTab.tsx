export default function ScannerTab() {
  return (
    <div className="-mx-6 -mb-6" style={{ height: 'calc(100vh - 112px)' }}>
      <iframe
        src="/scanner.html"
        title="Ticket Scanner"
        style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
        allow="clipboard-write"
      />
    </div>
  )
}
