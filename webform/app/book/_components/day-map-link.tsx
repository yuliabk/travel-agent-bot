'use client'
import { useState } from 'react'
export function DayMapLink({ places, destination, label }: { places: string[]; destination: string; label: string }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [url, setUrl] = useState('')
  async function openMap() {
    setBusy(true); setError(''); setUrl('')
    const popup = window.open('', '_blank')
    if (popup) { popup.opener = null; popup.document.title = 'מאתר נקודות מסלול...' }
    try {
      const response = await fetch('/api/map-route', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ places, destination }), signal: AbortSignal.timeout(55_000) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'לא ניתן לפתוח את המסלול')
      const parsed = new URL(data.url)
      if (parsed.origin !== 'https://www.google.com' || !parsed.pathname.startsWith('/maps/')) throw new Error('קישור המפה לא תקין')
      setUrl(data.url)
      if (popup) popup.location.href = data.url
    } catch (error) { popup?.close(); setError(error instanceof Error ? error.message : 'יצירת המפה נכשלה') }
    finally { setBusy(false) }
  }
  return <div className="mb-2"><button type="button" onClick={openMap} disabled={busy} className="text-primary underline disabled:opacity-50">{busy ? 'מאתר את המקומות על המפה...' : label}</button>{url && <a href={url} target="_blank" rel="noopener noreferrer" className="block text-sm underline">המסלול מוכן — פתיחה במפות</a>}{error && <p className="text-sm text-destructive mt-1">{error}</p>}</div>
}
