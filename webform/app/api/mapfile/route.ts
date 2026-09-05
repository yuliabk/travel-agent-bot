import { NextRequest } from 'next/server'
import { geocodePlaces, buildKml, buildKmlByDays, GeoPoint, DayPoints } from '@/lib/geocoding'

export const dynamic = 'force-dynamic'
export const maxDuration = 60

interface DayInput { label: string; places: string[]; destination?: string }

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const destination: string = typeof body?.destination === 'string' ? body.destination : ''
    const daysInput: DayInput[] = Array.isArray(body?.days) ? body.days.filter((d: any) => d && typeof d.label === 'string' && Array.isArray(d.places)).map((d: any) => ({ label: String(d.label), destination: typeof d.destination === 'string' ? d.destination : destination, places: (d.places as any[]).map((p) => String(p).trim()).filter(Boolean) })) : []
    const flatPlaces: string[] = Array.isArray(body?.places) ? body.places.map((p: any) => String(p).trim()).filter(Boolean) : []
    const allPlaces = daysInput.length > 0 ? daysInput.flatMap((d) => d.places) : flatPlaces
    if (!allPlaces.length) return new Response(JSON.stringify({ error: 'לא נמצאו נקודות ציון בתוכנית הטיול' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
    if (allPlaces.length > 80 || daysInput.length > 31) return Response.json({ error: 'התוכנית ארוכה מדי ליצירת מפה אחת' }, { status: 422 })
    const mapName = `מסלול הטיול${destination ? ` — ${destination}` : ''}`
    let kml: string, count = 0, missing = 0
    if (daysInput.length) {
      const groups = new Map<string, string[]>()
      for (const day of daysInput) { const city = day.destination || destination; groups.set(city, [...(groups.get(city) || []), ...day.places]) }
      if (groups.size > 8) return Response.json({ error: 'אפשר ליצור מפה לעד שמונה אזורים' }, { status: 422 })
      const located = new Map(await Promise.all(Array.from(groups, async ([city, places]) => [city, await geocodePlaces(places, city)] as const)))
      const days: DayPoints[] = daysInput.map(day => ({ label: day.label, points: Array.from(new Set(day.places)).map(name => (located.get(day.destination || destination) || []).find(point => point.name === name)).filter((point): point is GeoPoint => Boolean(point)) }))
      count = days.reduce((sum, day) => sum + day.points.length, 0)
      missing = Array.from(groups).reduce((sum, [city, names]) => sum + new Set(names).size - (located.get(city)?.length || 0), 0)
      kml = buildKmlByDays(days, mapName)
    } else {
      const points = await geocodePlaces(allPlaces, destination)
      count = points.length; missing = new Set(allPlaces).size - count
      kml = buildKml(points, mapName)
    }
    if (!count) return Response.json({ error: 'לא ניתן היה לאתר את נקודות הציון על המפה' }, { status: 422 })
    return new Response(kml, { status: 200, headers: { 'Content-Type': 'application/vnd.google-earth.kml+xml; charset=utf-8', 'X-Points-Count': String(count), 'X-Missing-Points': String(missing) } })
  } catch (e) {
    console.error('mapfile service failed')
    return new Response(JSON.stringify({ error: 'אירעה שגיאה ביצירת קובץ המפה' }), { status: 500, headers: { 'Content-Type': 'application/json' } })
  }
}
