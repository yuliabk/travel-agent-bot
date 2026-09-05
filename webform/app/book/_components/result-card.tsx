'use client'

import { useState } from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { Calendar, CheckCircle2, FileText, Map, MapPin, Printer, RefreshCw, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FormData } from './booking-wizard'
import { draftHtml, draftStyles, wordHtml, itineraryDays, routeUrl, mapsUrl } from '@/lib/draft-format'

interface Props { response: string; form: FormData }

export function ResultCard({ response, form }: Props) {
  const [mapLoading, setMapLoading] = useState(false)
  const [mapError, setMapError] = useState<string | null>(null)

  const extractPlaces = () => Array.from(new Set(Array.from((response ?? '').matchAll(/\[\[([^\]]+)\]\]/g)).map((m) => m[1].trim()).filter(Boolean)))

  const handlePrint = () => window.print()
  const handleWord = () => {
    const blob = new Blob(['\ufeff', wordHtml(response, form.destination)], { type: 'application/msword' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `trip-draft-${(form.destination || 'trip').replace(/[^\p{L}\p{N}_-]+/gu, '_')}.doc`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const handleMap = async () => {
    const places = extractPlaces()
    if (!places.length) { setMapError('לא נמצאו נקודות ציון למפה בטיוטה'); return }
    setMapLoading(true); setMapError(null)
    try {
      const res = await fetch('/api/mapfile', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ days: itineraryDays(response), places, destination: form.destination }) })
      if (!res.ok) throw new Error('map')
      const missing = Number(res.headers.get('X-Missing-Points') || 0)
      if (missing > 0) setMapError(`המפה הורדה, אך ${missing} מקומות לא אותרו. אפשר לפתוח אותם דרך הקישורים במסלול.`)
      const blob = new Blob([await res.text()], { type: 'application/vnd.google-earth.kml+xml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = `trip-map-${(form.destination || 'trip').replace(/[^\p{L}\p{N}_-]+/gu, '_')}.kml`; a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch { setMapError('קובץ המפה אינו זמין כרגע. הקישורים למקומות ולמסלול היומי זמינים למעלה.') }
    finally { setMapLoading(false) }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
      <div className="text-center mb-6">
        <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4"><CheckCircle2 className="h-8 w-8 text-green-600" /></div>
        <h2 className="font-display text-2xl font-bold">תוכנית הטיול שלכם מוכנה</h2>
        <p className="text-muted-foreground mt-1">זוהי טיוטה אוטומטית לבדיקה. הצעה סופית תינתן רק לאחר אישור סוכן נסיעות</p>
      </div>
      <div className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900" dir="rtl"><strong>לפני שמזמינים:</strong> זו תוכנית ראשונית. המחירים והזמינות יאושרו עם סוכן נסיעות לפני ההזמנה.</div>
      <div className="flex flex-wrap items-center justify-center gap-4 mb-6 text-sm text-muted-foreground">
        <span className="flex items-center gap-1.5"><MapPin className="h-4 w-4 text-primary" />{form.destination}</span>
        <span className="flex items-center gap-1.5"><Calendar className="h-4 w-4 text-primary" />{form.dateFrom} - {form.dateTo}</span>
        <span className="flex items-center gap-1.5"><Users className="h-4 w-4 text-primary" />{form.adults + form.children} נוסעים</span>
      </div>
      <style>{draftStyles}</style>
      <div className="print-card draft-body bg-card rounded-xl shadow-[var(--shadow-md)] p-5 sm:p-8 mb-6" dir="rtl" dangerouslySetInnerHTML={{ __html: draftHtml(response, form.destination) }} />
      {itineraryDays(response).length > 0 && <section className="mb-6 rounded-xl border bg-card p-5" dir="rtl">
        <h2 className="text-xl font-bold mb-2">המפה שלכם — לפי ימים</h2>
        <p className="text-sm text-muted-foreground mb-4">פתחו יום במפות Google, או בחרו מקום להצגה על המפה. בדקו זמני נסיעה לפני היציאה.</p>
        <div className="grid gap-4 sm:grid-cols-2">{itineraryDays(response).map((day, i) => <div key={i} className="rounded-lg border p-4">
          <h3 className="font-semibold mb-2">{day.label}</h3>
          {Array.from({ length: Math.ceil(Math.max(day.places.length - 1, 1) / 4) }, (_, part) => <a key={part} className="block text-primary underline mb-2" href={routeUrl(day.places.slice(part * 4, part * 4 + 5), form.destination)} target="_blank" rel="noopener noreferrer">פתיחת המסלול{day.places.length > 5 ? ` — חלק ${part + 1}` : ''}</a>)}
          <ul className="space-y-1">{day.places.map(place => <li key={place}><a className="text-sm underline" href={mapsUrl(place, form.destination)} target="_blank" rel="noopener noreferrer">{place}</a></li>)}</ul>
        </div>)}</div>
      </section>}
      <div className="no-print flex flex-col sm:flex-row items-center justify-center gap-3">
        <Button onClick={handlePrint} variant="outline"><Printer className="ml-2 h-4 w-4" />שמירת טיוטה כ-PDF</Button>
        <Button onClick={handleWord} variant="outline"><FileText className="ml-2 h-4 w-4" />הורדת טיוטה כ-Word</Button>
        <Button onClick={handleMap} variant="outline" disabled={mapLoading}><Map className="ml-2 h-4 w-4" />{mapLoading ? 'מכין מפה...' : 'הורדת קובץ מפה לייבוא'}</Button>
        <Button asChild><Link href="/book"><RefreshCw className="ml-2 h-4 w-4" />תכנון טיול נוסף</Link></Button>
      </div>
      {mapError && <p className="no-print text-center text-sm text-destructive mt-3">{mapError}</p>}
    </motion.div>
  )
}
