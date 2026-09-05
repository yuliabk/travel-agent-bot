import { NextRequest } from 'next/server'
import { geocodePlaces, buildKml, buildKmlByDays, GeoPoint, DayPoints } from '@/lib/geocoding'

export const dynamic = 'force-dynamic'

interface DayInput { label: string; places: string[] }

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const destination: string = typeof body?.destination === 'string' ? body.destination : ''
    const daysInput: DayInput[] = Array.isArray(body?.days) ? body.days.filter((d: any) => d && typeof d.label === 'string' && Array.isArray(d.places)).map((d: any) => ({ label: String(d.label), places: (d.places as any[]).map((p) => String(p).trim()).filter(Boolean) })) : []
    const flatPlaces: string[] = Array.isArray(body?.places) ? body.places.map((p: any) => String(p).trim()).filter(Boolean) : []
    const allPlaces = daysInput.length > 0 ? daysInput.flatMap((d) => d.places) : flatPlaces
    if (!allPlaces.length) return new Response(JSON.stringify({ error: 'לא נמצאו נקודות ציון בתוכנית הטיול' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
    const points = await geocodePlaces(allPlaces, destination)
    if (!points.length) return new Response(JSON.stringify({ error: 'לא ניתן היה לאתר את נקודות הציון על המפה' }), { status: 422, headers: { 'Content-Type': 'application/json' } })
    const mapName = `מסלול הטיול${destination ? ` — ${destination}` : ''}`
    let kml: string
    let count = points.length
    if (daysInput.length > 0) {
      const byName = new Map<string, GeoPoint>(); for (const p of points) byName.set(p.name.trim(), p)
      const dayPoints: DayPoints[] = []
      for (const d of daysInput) {
        const seen = new Set<string>(); const pts: GeoPoint[] = []
        for (const name of d.places) { const key = name.trim(); if (seen.has(key)) continue; const gp = byName.get(key); if (gp) { pts.push(gp); seen.add(key) } }
        if (pts.length) dayPoints.push({ label: d.label, points: pts })
      }
      if (!dayPoints.length) return new Response(JSON.stringify({ error: 'לא ניתן היה לאתר את נקודות הציון על המפה' }), { status: 422, headers: { 'Content-Type': 'application/json' } })
      count = dayPoints.reduce((n, d) => n + d.points.length, 0); kml = buildKmlByDays(dayPoints, mapName)
    } else { kml = buildKml(points, mapName) }
    return new Response(kml, { status: 200, headers: { 'Content-Type': 'application/vnd.google-earth.kml+xml; charset=utf-8', 'X-Points-Count': String(count) } })
  } catch (e) {
    console.error('mapfile route error:', e)
    return new Response(JSON.stringify({ error: 'אירעה שגיאה ביצירת קובץ המפה' }), { status: 500, headers: { 'Content-Type': 'application/json' } })
  }
}
