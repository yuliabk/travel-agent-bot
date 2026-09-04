'use client'

import { useState } from 'react'
import { FormData } from './booking-wizard'
import { Button } from '@/components/ui/button'
import { Printer, FileText, RefreshCw, MapPin, Calendar, Users, CheckCircle2, ExternalLink, Map, Loader2 } from 'lucide-react'
import { motion } from 'framer-motion'
import Link from 'next/link'

// Open a link reliably, even when the app runs inside an embedded/preview frame
// where target="_blank" popups may be blocked. Falls back to navigating the
// top-most frame so the link always opens.
function openLink(e: React.MouseEvent, href: string) {
  // Let the browser handle modified clicks (new tab/window, download, etc.)
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button === 1) return
  e.preventDefault()
  let win: Window | null = null
  try {
    win = window.open(href, '_blank')
  } catch {
    win = null
  }
  if (win) {
    try { (win as any).opener = null } catch {}
    return
  }
  // Popup blocked (typical inside sandboxed preview iframe) -> navigate top frame
  try {
    ;(window.top ?? window).location.href = href
  } catch {
    window.location.href = href
  }
}

interface Props {
  response: string
  form: FormData
}

function mapsUrl(place: string, destination: string) {
  const query = destination && !place.includes(destination) ? `${place}, ${destination}` : place
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`
}

// Convert [[place]] markers within a string into Google Maps links
function renderPlaces(text: string, destination: string, keyPrefix: string) {
  const parts = (text ?? '').split(/(\[\[[^\]]+\]\])/g)
  return parts.map((part: string, idx: number) => {
    if (part.startsWith('[[') && part.endsWith(']]')) {
      const place = part.slice(2, -2)
      return (
        <a
          key={`${keyPrefix}-${idx}`}
          href={mapsUrl(place, destination)}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => openLink(e, mapsUrl(place, destination))}
          className="inline-flex items-center gap-0.5 text-primary font-medium underline decoration-dotted underline-offset-2 hover:text-primary/80"
        >
          <MapPin className="h-3.5 w-3.5 shrink-0" />
          {place}
        </a>
      )
    }
    return <span key={`${keyPrefix}-${idx}`}>{part}</span>
  })
}

// Handle **bold** + [[place]] markers within a string
function renderBoldPlaces(text: string, destination: string, keyPrefix: string) {
  const parts = (text ?? '').split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part: string, idx: number) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={`${keyPrefix}-${idx}`} className="font-semibold">
          {renderPlaces(part.slice(2, -2), destination, `${keyPrefix}-b${idx}`)}
        </strong>
      )
    }
    return <span key={`${keyPrefix}-${idx}`}>{renderPlaces(part, destination, `${keyPrefix}-t${idx}`)}</span>
  })
}

function renderInline(text: string, destination: string) {
  // Split on markdown links [text](url) first (booking links), then bold + places
  const parts = (text ?? '').split(/(\[[^\]]+\]\((?:[^()]|\([^()]*\))*\))/g)
  return parts.map((part: string, idx: number) => {
    const m = part.match(/^\[([^\]]+)\]\(((?:[^()]|\([^()]*\))*)\)$/)
    if (m) {
      return (
        <a
          key={idx}
          href={m[2]}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => openLink(e, m[2])}
          className="inline-flex items-center gap-0.5 text-secondary font-semibold underline decoration-dotted underline-offset-2 hover:text-secondary/80"
        >
          <ExternalLink className="h-3.5 w-3.5 shrink-0" />
          {m[1]}
        </a>
      )
    }
    return <span key={idx}>{renderBoldPlaces(part, destination, `s${idx}`)}</span>
  })
}

// Escape text for safe HTML embedding
function esc(s: string) {
  return (s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

// Convert inline markdown (bold, [[place]] map links, [text](url) links) to HTML
function inlineToHtml(text: string, destination: string): string {
  // booking links first
  let parts = (text ?? '').split(/(\[[^\]]+\]\((?:[^()]|\([^()]*\))*\))/g)
  return parts
    .map((part) => {
      const m = part.match(/^\[([^\]]+)\]\(((?:[^()]|\([^()]*\))*)\)$/)
      if (m) {
        return `<a href="${esc(m[2])}">${esc(m[1])}</a>`
      }
      // bold + places
      return part
        .split(/(\*\*[^*]+\*\*)/g)
        .map((seg) => {
          const isBold = seg.startsWith('**') && seg.endsWith('**')
          const inner = isBold ? seg.slice(2, -2) : seg
          // [[place]] -> maps link
          const withPlaces = inner
            .split(/(\[\[[^\]]+\]\])/g)
            .map((p) => {
              if (p.startsWith('[[') && p.endsWith(']]')) {
                const place = p.slice(2, -2)
                return `<a href="${esc(mapsUrl(place, destination))}">${esc(place)}</a>`
              }
              return esc(p)
            })
            .join('')
          return isBold ? `<strong>${withPlaces}</strong>` : withPlaces
        })
        .join('')
    })
    .join('')
}

// Build a full Word-openable HTML document from the plan
function buildWordHtml(response: string, form: FormData): string {
  const dest = form?.destination ?? ''
  const body = (response ?? '')
    .split('\n')
    .map((line) => {
      const t = (line ?? '').trim()
      if (!t) return '<p></p>'
      if (t === '---' || t === '***') return '<hr/>'
      if (t.startsWith('### ')) return `<h3>${inlineToHtml(t.slice(4), dest)}</h3>`
      if (t.startsWith('## ')) return `<h2>${inlineToHtml(t.slice(3), dest)}</h2>`
      if (t.startsWith('# ')) return `<h1>${inlineToHtml(t.slice(2), dest)}</h1>`
      if (t.startsWith('- ') || t.startsWith('* ')) return `<li>${inlineToHtml(t.slice(2), dest)}</li>`
      if (/^\d+\.\s/.test(t)) return `<li>${inlineToHtml(t.replace(/^\d+\.\s/, ''), dest)}</li>`
      return `<p>${inlineToHtml(t, dest)}</p>`
    })
    .join('\n')

  const header = `
    <div style="text-align:center;border-bottom:2px solid #E8772E;padding-bottom:12px;margin-bottom:16px;">
      <h1 style="color:#E8772E;margin:0;">תוכנית הטיול שלך</h1>
      <p style="margin:6px 0 0;color:#555;">${esc(dest)} · ${esc(form?.dateFrom ?? '')} — ${esc(form?.dateTo ?? '')} · ${(form?.adults ?? 0) + (form?.children ?? 0)} נוסעים</p>
    </div>`

  return `<!DOCTYPE html>
<html dir="rtl" lang="he" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word">
<head>
<meta charset="utf-8"/>
<title>תוכנית הטיול</title>
<style>
  body { font-family: 'Arial', sans-serif; direction: rtl; text-align: right; color: #222; line-height: 1.6; }
  h1 { font-size: 22px; }
  h2 { color: #E8772E; font-size: 18px; border-bottom: 1px solid #eee; padding-bottom: 4px; margin-top: 18px; }
  h3 { font-size: 15px; margin-top: 12px; }
  a { color: #1F9E8F; }
  hr { border: none; border-top: 1px solid #ddd; margin: 14px 0; }
  li { margin-bottom: 4px; }
</style>
</head>
<body>
${header}
${body}
</body>
</html>`
}

interface DayPlaces {
  label: string
  places: string[]
}

// Matches a day heading line, e.g. "## יום 1: ...", "**יום שני**", "יום 3 –".
const DAY_HEADER_RE =
  /^\s*[#>*\-\s]*\**\s*יום\s+(?:\d+|ראשון|שני|שלישי|רביעי|חמישי|שישי|שביעי|שמיני|תשיעי|עשירי)\b/

// Extract [[place]] names grouped by day from the plan markdown.
// Each day becomes a separate layer on the map.
function extractPlacesByDay(text: string): DayPlaces[] {
  const lines = (text ?? '').split('\n')
  const days: DayPlaces[] = []
  let current: DayPlaces | null = null

  for (const line of lines) {
    if (DAY_HEADER_RE.test(line)) {
      const label =
        line
          .replace(/\[\[|\]\]/g, '')
          .replace(/[#>*_`]/g, '')
          .trim() || `יום ${days.length + 1}`
      current = { label, places: [] }
      days.push(current)
    }
    const re = /\[\[([^\]]+)\]\]/g
    let m: RegExpExecArray | null
    while ((m = re.exec(line)) !== null) {
      const name = m[1].trim()
      if (!name) continue
      if (!current) {
        current = { label: 'כללי', places: [] }
        days.push(current)
      }
      if (!current.places.includes(name)) current.places.push(name)
    }
  }

  return days.filter((d) => d.places.length > 0)
}

export function ResultCard({ response, form }: Props) {
  const [mapLoading, setMapLoading] = useState(false)
  const [mapError, setMapError] = useState<string | null>(null)

  const handlePrint = () => {
    window?.print?.()
  }

  const handleMap = async () => {
    setMapError(null)
    const days = extractPlacesByDay(response ?? '')
    const allPlaces = days.flatMap((d) => d.places)
    if (!allPlaces.length) {
      setMapError('לא נמצאו נקודות ציון למפה בתוכנית')
      return
    }
    setMapLoading(true)
    try {
      const res = await fetch('/api/mapfile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days, places: allPlaces, destination: form?.destination ?? '' }),
      })
      if (!res.ok) {
        let msg = 'לא הצלחנו ליצור את קובץ המפה, נסו שוב'
        try { const j = await res.json(); if (j?.error) msg = j.error } catch {}
        setMapError(msg)
        return
      }
      const kml = await res.text()
      const blob = new Blob([kml], { type: 'application/vnd.google-earth.kml+xml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const safeDest = (form?.destination ?? 'trip').replace(/[^\p{L}\p{N}_-]+/gu, '_').slice(0, 40)
      a.href = url
      a.download = `trip-map-${safeDest || 'trip'}.kml`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      console.error('Map export error:', err)
      setMapError('אירעה שגיאה ביצירת קובץ המפה, נסו שוב')
    } finally {
      setMapLoading(false)
    }
  }

  const handleWord = () => {
    try {
      const html = buildWordHtml(response ?? '', form)
      const blob = new Blob(['\ufeff', html], { type: 'application/msword' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const safeDest = (form?.destination ?? 'trip').replace(/[^\p{L}\p{N}_-]+/gu, '_').slice(0, 40)
      a.href = url
      a.download = `trip-plan-${safeDest || 'trip'}.doc`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      console.error('Word export error:', err)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Success header */}
      <div className="text-center mb-6">
        <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
          <CheckCircle2 className="h-8 w-8 text-green-600" />
        </div>
        <h2 className="font-display text-2xl font-bold">תוכנית הטיול שלכם מוכנה!</h2>
        <p className="text-muted-foreground mt-1">הנה התוכנית שהסוכן החכם הכין עבורכם</p>
      </div>

      {/* Trip summary bar */}
      <div className="flex flex-wrap items-center justify-center gap-4 mb-6 text-sm text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <MapPin className="h-4 w-4 text-primary" />
          {form?.destination ?? ''}
        </span>
        <span className="flex items-center gap-1.5">
          <Calendar className="h-4 w-4 text-primary" />
          {form?.dateFrom ?? ''} — {form?.dateTo ?? ''}
        </span>
        <span className="flex items-center gap-1.5">
          <Users className="h-4 w-4 text-primary" />
          {(form?.adults ?? 0) + (form?.children ?? 0)} נוסעים
        </span>
      </div>

      {/* AI response card */}
      <div className="print-card bg-card rounded-xl shadow-[var(--shadow-md)] p-6 sm:p-8 mb-6">
        <div className="prose prose-sm max-w-none" dir="rtl">
          {(response ?? '').split('\n')?.map((line: string, i: number) => {
            const trimmed = line?.trim() ?? ''
            if (!trimmed) return <br key={i} />
            if (trimmed === '---' || trimmed === '***') return <hr key={i} className="my-4 border-border" />
            if (trimmed.startsWith('### ')) return <h4 key={i} className="font-display text-base font-semibold mt-2 mb-1">{renderInline(trimmed.slice(4), form?.destination ?? '')}</h4>
            if (trimmed.startsWith('## ')) return <h3 key={i} className="font-display text-lg font-semibold mt-3 mb-1">{renderInline(trimmed.slice(3), form?.destination ?? '')}</h3>
            if (trimmed.startsWith('# ')) return <h2 key={i} className="font-display text-xl font-bold mt-4 mb-2 text-primary">{renderInline(trimmed.slice(2), form?.destination ?? '')}</h2>
            if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) return <li key={i} className="mr-4 mb-1 list-disc">{renderInline(trimmed.slice(2), form?.destination ?? '')}</li>
            if (/^\d+\.\s/.test(trimmed)) return <li key={i} className="mr-4 mb-1 list-decimal">{renderInline(trimmed.replace(/^\d+\.\s/, ''), form?.destination ?? '')}</li>
            return <p key={i} className="mb-2 leading-relaxed">{renderInline(trimmed, form?.destination ?? '')}</p>
          })}
        </div>
      </div>

      {/* Actions */}
      <div className="no-print flex flex-col sm:flex-row items-center justify-center gap-3">
        <Button onClick={handlePrint} variant="outline">
          <Printer className="ml-2 h-4 w-4" />
          הדפסה / שמירה כ-PDF
        </Button>
        <Button onClick={handleWord} variant="outline">
          <FileText className="ml-2 h-4 w-4" />
          הורדת דו״ח כ-Word
        </Button>
        <Button onClick={handleMap} variant="outline" disabled={mapLoading}>
          {mapLoading ? (
            <Loader2 className="ml-2 h-4 w-4 animate-spin" />
          ) : (
            <Map className="ml-2 h-4 w-4" />
          )}
          {mapLoading ? 'מכין מפה...' : 'הורדת מפת מסלול (ל-Google Maps)'}
        </Button>
        <Button asChild>
          <Link href="/book">
            <RefreshCw className="ml-2 h-4 w-4" />
            תכנון טיול נוסף
          </Link>
        </Button>
        <Button variant="secondary" asChild>
          <Link href="/thank-you">חזרה לדף הבית</Link>
        </Button>
      </div>

      {mapError && (
        <p className="no-print text-center text-sm text-destructive mt-3">{mapError}</p>
      )}
      <p className="no-print text-center text-xs text-muted-foreground mt-3 max-w-md mx-auto">
קובץ המפה (KML) מחולק לפי ימים — לכל יום שכבה נפרדת בצבע משלו. ניתן לייבא אותו ל-Google My Maps (אתר/אפליקציה) ולהשתמש בו גם ללא אינטרנט.
      </p>
    </motion.div>
  )
}
