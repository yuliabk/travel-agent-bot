'use client'

import { useState } from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { Calendar, CheckCircle2, FileText, Map, MapPin, Printer, RefreshCw, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FormData } from './booking-wizard'

interface Props { response: string; form: FormData }

function mapsUrl(place: string, destination: string) {
  const q = destination && !place.includes(destination) ? `${place}, ${destination}` : place
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`
}

function renderInline(text: string, destination: string) {
  return (text ?? '').split(/(\[\[[^\]]+\]\])/g).map((part, i) => {
    if (part.startsWith('[[') && part.endsWith(']]')) {
      const place = part.slice(2, -2)
      return <a key={i} href={mapsUrl(place, destination)} target="_blank" rel="noopener noreferrer" className="text-primary font-medium underline decoration-dotted underline-offset-2">{place}</a>
    }
    const bold = part.match(/^\*\*(.+)\*\*$/)
    return bold ? <strong key={i}>{bold[1]}</strong> : <span key={i}>{part}</span>
  })
}

function wordHtml(response: string, form: FormData) {
  const esc = (s: string) => (s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const body = response.split('\n').map((line) => {
    const t = line.trim()
    if (!t) return '<br/>'
    if (t.startsWith('## ')) return `<h2>${esc(t.slice(3))}</h2>`
    if (t.startsWith('# ')) return `<h1>${esc(t.slice(2))}</h1>`
    if (t.startsWith('- ') || t.startsWith('* ')) return `<li>${esc(t.slice(2))}</li>`
    return `<p>${esc(t)}</p>`
  }).join('')
  return `<!doctype html><html dir="rtl" lang="he"><meta charset="utf-8"><style>body{font-family:Arial;direction:rtl;line-height:1.6}h1,h2{color:#E8772E} .draft{background:#fff7ed;padding:10px;border:1px solid #fdba74}</style><body><div class="draft"><b>AI DRAFT - לא הצעה סופית</b></div><h1>טיוטת טיול - ${esc(form.destination)}</h1>${body}</body></html>`
}

export function ResultCard({ response, form }: Props) {
  const [mapLoading, setMapLoading] = useState(false)
  const [mapError, setMapError] = useState<string | null>(null)

  const extractPlaces = () => Array.from(new Set(Array.from((response ?? '').matchAll(/\[\[([^\]]+)\]\]/g)).map((m) => m[1].trim()).filter(Boolean)))

  const handlePrint = () => window.print()
  const handleWord = () => {
    const blob = new Blob(['\ufeff', wordHtml(response, form)], { type: 'application/msword' })
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
      const res = await fetch('/api/mapfile', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ places, destination: form.destination }) })
      if (!res.ok) throw new Error('map')
      const blob = new Blob([await res.text()], { type: 'application/vnd.google-earth.kml+xml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = `trip-map-${(form.destination || 'trip').replace(/[^\p{L}\p{N}_-]+/gu, '_')}.kml`; a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch { setMapError('לא הצלחנו ליצור את קובץ המפה. נסו שוב.') }
    finally { setMapLoading(false) }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
      <div className="text-center mb-6">
        <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4"><CheckCircle2 className="h-8 w-8 text-green-600" /></div>
        <h2 className="font-display text-2xl font-bold">טיוטת ה-AI שלכם מוכנה</h2>
        <p className="text-muted-foreground mt-1">זוהי טיוטה אוטומטית לבדיקה. הצעה סופית תינתן רק לאחר אישור סוכן נסיעות</p>
      </div>
      <div className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900" dir="rtl"><strong>AI DRAFT - לא הצעה סופית:</strong> פרטים מסחריים, כאשר קיימים, חייבים להיות מגובים ב-Evidence. כל שינוי לאחר אישור דורש אישור מחדש.</div>
      <div className="flex flex-wrap items-center justify-center gap-4 mb-6 text-sm text-muted-foreground">
        <span className="flex items-center gap-1.5"><MapPin className="h-4 w-4 text-primary" />{form.destination}</span>
        <span className="flex items-center gap-1.5"><Calendar className="h-4 w-4 text-primary" />{form.dateFrom} - {form.dateTo}</span>
        <span className="flex items-center gap-1.5"><Users className="h-4 w-4 text-primary" />{form.adults + form.children} נוסעים</span>
      </div>
      <div className="print-card bg-card rounded-xl shadow-[var(--shadow-md)] p-6 sm:p-8 mb-6"><div className="prose prose-sm max-w-none" dir="rtl">{response.split('\n').map((line, i) => { const t=line.trim(); if(!t)return <br key={i}/>; if(t==='---')return <hr key={i} className="my-4 border-border"/>; if(t.startsWith('## '))return <h3 key={i} className="font-display text-lg font-semibold mt-3 mb-1">{renderInline(t.slice(3), form.destination)}</h3>; if(t.startsWith('# '))return <h2 key={i} className="font-display text-xl font-bold mt-4 mb-2 text-primary">{renderInline(t.slice(2), form.destination)}</h2>; if(t.startsWith('- ')||t.startsWith('* '))return <li key={i} className="mr-4 mb-1 list-disc">{renderInline(t.slice(2), form.destination)}</li>; return <p key={i} className="mb-2 leading-relaxed">{renderInline(t, form.destination)}</p>})}</div></div>
      <div className="no-print flex flex-col sm:flex-row items-center justify-center gap-3">
        <Button onClick={handlePrint} variant="outline"><Printer className="ml-2 h-4 w-4" />שמירת טיוטה כ-PDF</Button>
        <Button onClick={handleWord} variant="outline"><FileText className="ml-2 h-4 w-4" />הורדת טיוטה כ-Word</Button>
        <Button onClick={handleMap} variant="outline" disabled={mapLoading}><Map className="ml-2 h-4 w-4" />{mapLoading ? 'מכין מפה...' : 'הורדת מפת מסלול'}</Button>
        <Button asChild><Link href="/book"><RefreshCw className="ml-2 h-4 w-4" />תכנון טיול נוסף</Link></Button>
      </div>
      {mapError && <p className="no-print text-center text-sm text-destructive mt-3">{mapError}</p>}
    </motion.div>
  )
}
