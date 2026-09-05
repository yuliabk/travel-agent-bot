'use client'
import { useEffect, useRef, useState } from 'react'
type Choice = { name: string; description: string; airports: { code: string; name: string }[] }
export function DestinationLookup({ value, onChoose, lodging = false }: { value: string; onChoose: (name: string, airport?: string) => void; lodging?: boolean }) {
  const [choices, setChoices] = useState<Choice[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const sequence = useRef(0)
  useEffect(() => { sequence.current++; setChoices([]); setMessage(''); setBusy(false) }, [value])
  async function lookup() {
    const current = ++sequence.current
    setBusy(true); setChoices([]); setMessage('')
    try {
      const response = await fetch('/api/destinations', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: value }), signal: AbortSignal.timeout(20_000) })
      const data = await response.json()
      if (current !== sequence.current) return
      if (!response.ok) { setMessage(data.error || 'לא ניתן לזהות כרגע'); return }
      setChoices(data.suggestions ?? [])
      if (!data.suggestions?.length) setMessage('לא נמצאה התאמה ברורה. הוסיפו מדינה או נסו את שם העיר באנגלית. אפשר גם להזין יעד ושדה נחיתה ידנית.')
    } catch { if (current === sequence.current) setMessage('החיפוש לא הושלם. נסו שוב.') }
    finally { if (current === sequence.current) setBusy(false) }
  }
  return <div className="mt-2 space-y-2" aria-live="polite">
    <button type="button" className="text-sm text-primary underline disabled:opacity-50" disabled={busy || value.trim().length < 2} onClick={lookup}>{busy ? 'מזהה יעד...' : 'זיהוי שם היעד וחיפוש ערים נוספות'}</button>
    {message && <p className="text-sm text-muted-foreground">{message}</p>}
    {choices.length > 0 && <p className="text-sm">בחרו את העיר הנכונה לפי השם והמדינה:</p>}
    {choices.map(choice => <div key={choice.name} className="rounded border p-2"><strong className="text-sm">{choice.name}</strong><p className="text-xs text-muted-foreground">{choice.description}</p>{lodging || !choice.airports.length ? <button type="button" className="underline text-sm" onClick={() => onChoose(choice.name)}>בחירת המקום</button> : choice.airports.map(airport => <button key={airport.code} type="button" className="block text-sm underline mt-1" onClick={() => onChoose(choice.name, airport.code)}>בחירת העיר ונחיתה ב־{airport.name} ({airport.code})</button>)}</div>)}
  </div>
}
