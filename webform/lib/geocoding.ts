import { canonicalDestination } from './airports'
export interface GeoPoint { name: string; lat: number; lng: number }
export async function geocodePlaces(places: string[], destination: string): Promise<GeoPoint[]> {
  const base = (process.env.TRAVEL_AGENT_API_URL ?? '').replace(/\/$/, '')
  const token = process.env.TRAVEL_AGENT_WEB_TOKEN
  if (!base || !token) throw new Error('Map service unavailable')
  const unique = Array.from(new Set(places.map(p => p.trim()).filter(Boolean)))
  if (unique.length > 40) throw new Error('Too many places')
  const response = await fetch(`${base}/v1/web/map-points`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ places: unique, destination: canonicalDestination(destination) }),
    cache: 'no-store', signal: AbortSignal.timeout(55_000),
  })
  if (!response.ok) throw new Error('Map service unavailable')
  const data = await response.json()
  return (data.points ?? []).filter((p: GeoPoint) => unique.includes(p.name) && Number.isFinite(p.lat) && Number.isFinite(p.lng) && Math.abs(p.lat) <= 90 && Math.abs(p.lng) <= 180)
}
function esc(s:string){return(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
export function buildKml(points:GeoPoint[],mapName:string){const marks=points.map((p,i)=>`<Placemark><name>${esc(`${i+1}. ${p.name}`)}</name><Point><coordinates>${p.lng},${p.lat},0</coordinates></Point></Placemark>`).join('\n');return `<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>${esc(mapName)}</name>${marks}</Document></kml>`}
export interface DayPoints{label:string;points:GeoPoint[]}
export function buildKmlByDays(days:DayPoints[],mapName:string){const folders=days.map((d)=>`<Folder><name>${esc(d.label)}</name>${d.points.map((p,i)=>`<Placemark><name>${esc(`${i+1}. ${p.name}`)}</name><description>${esc(`${d.label} - ${p.name}`)}</description><Point><coordinates>${p.lng},${p.lat},0</coordinates></Point></Placemark>`).join('')}</Folder>`).join('');return `<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>${esc(mapName)}</name>${folders}</Document></kml>`}
