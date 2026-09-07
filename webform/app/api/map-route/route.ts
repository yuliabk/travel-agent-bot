import { NextRequest } from 'next/server'
import { geocodePlaces } from '@/lib/geocoding'
export const dynamic = 'force-dynamic'
export const maxDuration = 60
export async function POST(request: NextRequest) {
  try {
    const { places, destination } = await request.json()
    if (!Array.isArray(places) || !places.length || places.length > 5 || places.some(p => typeof p !== 'string' || !p.trim() || p.length > 300) || typeof destination !== 'string' || !destination.trim() || destination.length > 200) return Response.json({ error: 'חסרים מקום ועיר ליצירת המסלול.' }, { status: 422 })
    const names = Array.from(new Set<string>(places.map((p: string) => p.trim())))
    const points = await geocodePlaces(names, destination)
    const missing = names.filter(name => !points.some(point => point.name === name))
    if (missing.length) return Response.json({ error: `לא אותרו בוודאות: ${missing.join(', ')}. אפשר לפתוח כל מקום בנפרד. המסלול לא נפתח מהמיקום הנוכחי.`, missing }, { status: 422 })
    const coordinates = names.map(name => { const point = points.find(p => p.name === name)!; return `${point.lat},${point.lng}` })
    const url = coordinates.length === 1 ? `https://www.google.com/maps/search/?${new URLSearchParams({ api: '1', query: coordinates[0] })}` : `https://www.google.com/maps/dir/?${new URLSearchParams({ api: '1', origin: coordinates[0], destination: coordinates.at(-1)!, ...(coordinates.length > 2 ? { waypoints: coordinates.slice(1, -1).join('|') } : {}) })}`
    return Response.json({ url, points }, { headers: { 'Cache-Control': 'no-store' } })
  } catch { return Response.json({ error: 'איתור המקומות לא הושלם. נסו שוב או פתחו מקום בנפרד.' }, { status: 502 }) }
}
